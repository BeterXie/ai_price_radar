"""Main-host scheduler/publisher. No remote worker receives DB credentials."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from common import session_for, utcnow
from app.models import CollectorJob, SourceIntake, SourceCandidate
from common import Shop
from app.services.collector_protocol import parse_bundle
from connectors.base import SourceFetchError, SourceUnavailableError
from connectors import kmdian
from publish_catalog import (
    PreparedSource, SourceSpec, _current_snapshot_id, _eligible_publish_sources, _prepare_sources,
    _publish_prepared_sources, approved_dujiao_sources, approved_intake_sources, merge_sources,
    resolve_intake_shop,
    load_merchant_sources,
)

def import_legacy_approvals(db, crawler_db: Path, merchant_sources: Path | None = None):
    """One-time cutover: all future approval changes use the main database."""
    from price_radar_http import PinnedHTTPSClient
    if not crawler_db.is_file():
        raise ValueError('authoritative crawler approval database is missing')
    sources = [('dujiao_next', url) for url in approved_dujiao_sources(crawler_db)]
    if merchant_sources and merchant_sources.is_file():
        sources += [('merchant_json', url) for url in load_merchant_sources(merchant_sources)]
    added = skipped = 0
    for platform, url in sources:
        canonical = PinnedHTTPSClient.normalize_url(url)
        if platform == 'dujiao_next':
            canonical = canonical.rstrip('/')
        existing = db.scalar(select(SourceIntake).where(
            or_(SourceIntake.source_key == canonical, func.rtrim(SourceIntake.source_url, '/') == canonical.rstrip('/'))))
        hidden = db.scalar(select(Shop.id).where(Shop.platform == platform, Shop.is_visible.is_(False),
            func.rtrim(Shop.source_url, '/') == canonical.rstrip('/')).limit(1))
        disabled = db.scalar(select(SourceCandidate.id).where(SourceCandidate.status.in_(('disabled','rejected')),
            or_(func.rtrim(SourceCandidate.canonical_url, '/') == canonical.rstrip('/'),
                func.rtrim(SourceCandidate.detected_source_url, '/') == canonical.rstrip('/'))).limit(1))
        if existing or hidden or disabled:
            skipped += 1
            continue
        db.add(SourceIntake(source_type=platform, detected_platform=platform, source_key=canonical,
            source_url=canonical, contact_email='', status='approved', approved_at=utcnow(),
            decision_note='Migrated existing local approval to authoritative main database'))
        db.flush()
        added += 1
    db.commit()
    return {'imported_approvals': added, 'preserved_existing_or_hidden': skipped}


def enqueue(db, kind: str, release: str):
    now = utcnow()
    # A repeatedly crashing worker must not keep the lane occupied forever.
    db.execute(update(CollectorJob).where(CollectorJob.status.in_(("running", "receiving", "retry")), CollectorJob.attempts >= 5,
        CollectorJob.lease_expires_at < now).values(status="failed", active_lane=None, error="collector retry limit reached"))
    db.execute(update(CollectorJob).where(CollectorJob.release != release,
        CollectorJob.status.in_(("queued", "collected", "running", "receiving", "retry")),
        CollectorJob.published_snapshot_id.is_(None)).values(status="failed", active_lane=None, lease_token="", error="collector release retired"))
    lane = "discovery" if kind == "discover" else "catalog"
    if kind == 'scan':
        db.execute(update(CollectorJob).where(CollectorJob.status.in_(("published", "failed")),
            CollectorJob.followup_kind == 'scan').values(followup_kind=''))
    active = db.scalar(select(CollectorJob).where(CollectorJob.active_lane == lane))
    if active:
        if kind == "scan" and active.kind == "inventory":
            active.followup_kind = "scan"
        db.commit()
        return {"job_id": active.id, "created": False, "status": active.status}
    specs = []
    if kind != "discover":
        if os.getenv('COLLECTOR_LDXP_ENABLED', 'true').casefold() in {'1','true','yes','on'}:
            specs.append(SourceSpec("ldxp", "/data/ldxp_crawler.db"))
        if kind == "scan":
            specs += approved_intake_sources(db, now=now)
        specs = merge_sources(specs)
        specs = _eligible_publish_sources(db, specs, now=now)[0]
        if not specs and kind == 'inventory':
            db.commit()
            return {'created':False, 'status':'empty', 'reason':'no approved sources'}
    manifest = []
    for spec in specs:
        row = {"connector": spec.connector, "source": spec.source, "intake_ids": list(spec.intake_ids)}
        if spec.connector == "16688":
            shop = resolve_intake_shop(db, source_url=spec.source, source_key=spec.source,
                source_type={"woocommerce-store": "woocommerce"}.get(spec.connector, spec.connector.replace("-", "_")))
            if shop:
                row["shop_token"] = shop["token"]
        manifest.append(row)
    job = CollectorJob(id=str(uuid4()), kind=kind, release=release, active_lane=lane, sources=manifest,
                       baseline_snapshot_id=_current_snapshot_id(db))
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = db.scalar(select(CollectorJob).where(CollectorJob.active_lane == lane))
        if active is None:
            raise
        return {"job_id": active.id, "created": False, "status": active.status}
    return {"job_id": job.id, "created": True, "status": job.status, "sources": len(specs)}


def publish_ready(db, result_dir: Path, *, release: str | None = None):
    if not release:
        raise ValueError("collector release is required for publication")
    job = db.scalar(select(CollectorJob).where(CollectorJob.status.in_(("collected", "publishing")))
                    .order_by(CollectorJob.created_at).with_for_update(skip_locked=True).limit(1))
    if job is None:
        db.rollback()
        return {"published": False, "reason": "no collected job"}
    identity = job.id
    if release and job.release != release and job.published_snapshot_id is None:
        job.status, job.active_lane, job.error = "failed", None, "collector release retired before publication"
        db.commit()
        return {"job_id": identity, "retired": True}
    if job.kind == "discover":
        job.status, job.active_lane = "published", None
        db.commit()
        return {"job_id": identity, "discovery_complete": True}
    if job.published_snapshot_id is not None:
        snapshot_id = job.published_snapshot_id
        db.rollback()
        from common import publication_lock
        from export_snapshot import DEFAULT_OUTPUT_DIR, export_public_snapshot
        from export_alerts import export_snapshot_alerts, _encoded_report
        with publication_lock(db):
            if _current_snapshot_id(db) == snapshot_id:
                existing = DEFAULT_OUTPUT_DIR / "alerts-latest.json"
                report = json.loads(existing.read_text()) if existing.is_file() else None
                reports = []
                def before_publish(snapshot):
                    if report and report.get('snapshot_id') == snapshot_id:
                        reports.append(report)
                        return
                    from app.services.alert_reports import build_alert_report, public_offer_prices
                    baseline = job.result_summary.get('public_baseline_snapshot_id')
                    previous = json.loads((DEFAULT_OUTPUT_DIR / 'v1' / 'snapshots' / f'{baseline}.json').read_text(encoding='utf-8')) if baseline is not None else None
                    reports.append(build_alert_report(snapshot, [], previous_prices=public_offer_prices(previous) if previous else {}, compare_all=True))
                    _encoded_report(reports[-1])
                export_public_snapshot(db, snapshot_id, before_publish=before_publish)
                export_snapshot_alerts(db, snapshot_id, [], output_dir=DEFAULT_OUTPUT_DIR, prepared_report=reports[0])
                db.commit()
        # Recover files, never import or resend an already committed batch.
        job = db.get(CollectorJob, identity, populate_existing=True)
        errors = finish_onboarding(db, job, result_dir)
        job.status, job.active_lane = "published", None
        job.error = "onboarding_pending" if errors else "Recovered committed snapshot; notifications not replayed"
        job.updated_at = utcnow()
        db.commit()
        return {"job_id": identity, "recovered_snapshot": snapshot_id}
    specs = [SourceSpec(s["connector"], s["source"], tuple(s["intake_ids"])) for s in job.sources]
    selected = {i: spec for spec in specs for i in spec.intake_ids}
    filename = result_dir / job.result_file
    if filename.parent.resolve() != result_dir.resolve() or not filename.name.startswith(identity + "-"):
        raise ValueError("invalid stored collector result path")
    kind, raw_sources = job.kind, job.sources
    preserve_local_ldxp = kind == 'scan' and not any(spec.connector == 'ldxp' for spec in specs)
    expected_snapshot = job.baseline_snapshot_id
    if any(spec.connector != 'ldxp' and not spec.intake_ids for spec in specs):
        job.status, job.active_lane, job.error = "failed", None, "source has no authoritative intake approval"
        db.commit()
        return {"job_id": identity, "approval_changed": True}
    job.status = "publishing"
    db.commit()
    try:
        with tempfile.TemporaryDirectory(prefix="collector-publish-") as directory:
            results = parse_bundle(filename, identity, raw_sources, Path(directory))
            prepared = []
            for spec, item in zip(specs, results, strict=True):
                error = None
                if item["status"] == "fetch_failed":
                    error = SourceFetchError(item["error"])
                elif item["status"] == "unavailable":
                    error = SourceUnavailableError(item["error"])
                rows = PreparedSource(spec, Path(item["path"]), error=error)
                if error is None:
                    rows.shop_tokens = {row["token"] for row in rows.records()}
                prepared.append(rows)
            validate_batch_identity(db, prepared)
            db.rollback()
            # This credentialed platform feed runs only on the whitelisted main
            # host. Worker manifests and uploaded records never receive its key.
            # Finish collection before acquiring publication locks/connections.
            if kind == "scan":
                kmdian_key = os.getenv(kmdian.API_KEY_ENV, "").strip()
                if kmdian_key:
                    platform_directory = Path(directory) / "platform-api"
                    platform_directory.mkdir()
                    prepared.extend(_prepare_sources(
                        [SourceSpec("kmdian", kmdian.API_URL)], platform_directory,
                    ))
            result = _publish_prepared_sources(db, prepared, [], expected_snapshot_id=expected_snapshot,
                expected_intakes=selected, source_label="collector:" + identity,
                carry_forward_current=kind == "inventory", dry_run=False, started_at=utcnow(), collector_job_id=identity,
                preserve_local_ldxp=preserve_local_ldxp,
                before_import=lambda active_prepared: validate_batch_identity(db, active_prepared))
        job = db.get(CollectorJob, identity, populate_existing=True)
        onboarding_errors = finish_onboarding(db, job, result_dir)
        job.status, job.active_lane = "published", None
        job.updated_at = utcnow()
        job.error = "onboarding_pending" if onboarding_errors else ""
        db.commit()
        return {"job_id": identity, "published": True, "snapshot_id": result.snapshot_id,
                "imports": [item.to_dict() for item in result.imports]}
    except Exception as exc:
        db.rollback()
        job = db.get(CollectorJob, identity, populate_existing=True)
        if job.published_snapshot_id is None:
            job.status, job.active_lane = "failed", None
        else:
            job.status = "publishing"
        job.error = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        raise


def validate_batch_identity(db, prepared):
    owners, intake_tokens = {}, {}
    for source in prepared:
        if source.error is not None:
            continue
        for row in source.records():
            token, platform = row["token"], row["source_platform"]
            if owners.setdefault(token, platform) != platform:
                raise ValueError("collector batch contains conflicting shop ownership")
            if row.get("intake_id") is not None:
                intake_tokens.setdefault(row["intake_id"], set()).add(token.casefold())
    tokens = list(owners)
    for start in range(0, len(tokens), 500):
        for shop in db.scalars(select(Shop).where(Shop.token.in_(tokens[start:start + 500]))):
            if shop.platform != owners[shop.token]:
                raise ValueError("collector result conflicts with existing shop ownership")
    ids = list(intake_tokens)
    for start in range(0, len(ids), 500):
        found = {intake.id: intake for intake in db.scalars(select(SourceIntake).where(SourceIntake.id.in_(ids[start:start + 500])))}
        for identity in ids[start:start + 500]:
            intake = found.get(identity)
            if not intake or intake.source_type != "ldxp" or intake_tokens[identity] != {intake.source_key.casefold()}:
                raise ValueError("collector onboarding identity mismatch")


def finish_onboarding(db, job, directory):
    from ldxp_intake import collect_intake_metadata, published_offer_counts, onboard_published_intakes
    skipped = set()
    plan = job.result_summary.get('onboarding_plan')
    if plan is None:
        plan = []
        with tempfile.TemporaryDirectory(prefix="collector-onboard-") as output:
            summaries = parse_bundle(directory / job.result_file, job.id, job.sources, Path(output))
            for spec, summary in zip(job.sources, summaries, strict=True):
                if spec["connector"] != "ldxp" or summary["status"] != "ok":
                    continue
                with Path(summary["path"]).open(encoding="utf-8") as stream:
                    tokens, attempts = collect_intake_metadata(json.loads(line) for line in stream)
                for identity, count in published_offer_counts(db, job.published_snapshot_id, tokens).items():
                    plan.append({'id':identity, 'count':count, 'attempt':attempts[identity], 'tokens':list(tokens[identity])})
        job.result_summary = {**job.result_summary, 'onboarding_plan': plan}
        db.commit()
    counts, attempts = {}, {}
    for item in plan:
        identity = item['id']
        intake = db.get(SourceIntake, identity, populate_existing=True)
        if not intake or intake.source_type != 'ldxp' or {t.casefold() for t in item['tokens']} != {intake.source_key.casefold()} or intake.attempt_count != item['attempt'] or intake.status != 'validated':
            skipped.add(identity)
            continue
        counts[identity], attempts[identity] = item['count'], item['attempt']
    errors = onboard_published_intakes(counts, attempts, api_url=os.getenv('INTAKE_API_URL',''), worker_key=os.getenv('INTAKE_WORKER_KEY',''))
    if skipped:
        job.result_summary = {**job.result_summary, "onboarding_skipped_stale_intake_ids": sorted(skipped)}
    return errors


def cleanup_results(db, directory):
    cutoff = utcnow() - timedelta(days=2)
    for job in db.scalars(select(CollectorJob).where(CollectorJob.status.in_(("published", "failed")), CollectorJob.error != 'onboarding_pending', CollectorJob.updated_at < cutoff,
                                                  CollectorJob.result_file != "").limit(100)):
        path = directory / job.result_file
        if path.parent.resolve() == directory.resolve() and path.name.startswith(job.id + "-"):
            path.unlink(missing_ok=True)
            job.result_file = ""
    db.commit()
    referenced = set(db.scalars(select(CollectorJob.result_file).where(CollectorJob.result_file != "")))
    for path in directory.glob("*"):
        try:
            if path.name not in referenced and path.stat().st_mtime < cutoff.timestamp():
                if path.name.startswith("validate-") and path.is_dir():
                    shutil.rmtree(path)
                elif path.suffix == ".gz":
                    path.unlink()
        except FileNotFoundError:
            continue


def retry_onboarding(db, directory):
    job = db.scalar(select(CollectorJob).where(CollectorJob.status == 'published', CollectorJob.error == 'onboarding_pending',
        CollectorJob.updated_at < utcnow() - timedelta(minutes=5)).order_by(CollectorJob.updated_at).limit(1))
    if not job:
        return
    try:
        errors = finish_onboarding(db, job, directory)
    except (OSError, ValueError) as exc:
        errors = [{'error': type(exc).__name__ + ': ' + str(exc)[:300]}]
    attempts = job.result_summary.get('onboarding_retries', 0) + 1
    job.result_summary = {**job.result_summary, 'onboarding_retries': attempts, 'onboarding_errors': errors}
    job.error = ('onboarding_pending' if attempts < 5 else 'onboarding needs operator attention') if errors else ''
    job.updated_at = utcnow()
    db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enqueue", "publish", "status", "import-approvals"))
    parser.add_argument("--kind", choices=("scan", "inventory", "discover"), default="inventory")
    parser.add_argument("--release", default=os.getenv("COLLECTOR_RELEASE", ""))
    parser.add_argument("--crawler-db", type=Path)
    parser.add_argument("--merchant-sources", type=Path)
    parser.add_argument("--results", type=Path, default=Path(os.getenv("COLLECTOR_RESULTS_DIR", "/data/collector-results")))
    args = parser.parse_args()
    with session_for(os.environ["DATABASE_URL"]) as db:
        if args.action == "enqueue":
            if not args.release:
                parser.error("COLLECTOR_RELEASE is required")
            result = enqueue(db, args.kind, args.release)
        elif args.action == 'import-approvals':
            if not args.crawler_db:
                parser.error('--crawler-db is required for one-time approval migration')
            result = import_legacy_approvals(db, args.crawler_db, args.merchant_sources)
        elif args.action == "publish":
            result = publish_ready(db, args.results, release=args.release)
            cleanup_results(db, args.results)
            retry_onboarding(db, args.results)
            pending = db.scalar(select(CollectorJob).where(CollectorJob.status.in_(("published", "failed")), CollectorJob.followup_kind == "scan").limit(1))
            if pending:
                enqueue(db, "scan", args.release)
        else:
            result = [{"id": j.id, "kind": j.kind, "status": j.status, "worker": j.worker_id,
                       "attempts": j.attempts, "updated_at": j.updated_at.isoformat(), "summary": j.result_summary,
                       "snapshot": j.published_snapshot_id, "error": j.error}
                      for j in db.scalars(select(CollectorJob).order_by(CollectorJob.created_at.desc()).limit(10))]
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
