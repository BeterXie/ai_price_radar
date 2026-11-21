import gzip
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from common import session_for, CatalogSnapshot
from app.database import Base as ApiBase
from app.models import CollectorJob
from app.services.collector_protocol import SCHEMA
from app.services import notification_hub
from collector_jobs import enqueue, publish_ready
from connectors import CONNECTORS


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    import export_snapshot
    monkeypatch.setattr(export_snapshot, 'DEFAULT_OUTPUT_DIR', tmp_path / 'public')
    monkeypatch.setattr(notification_hub, 'dispatch_price_changes', lambda *args, **kwargs: None)
    db = session_for('sqlite://')
    ApiBase.metadata.create_all(db.get_bind())
    yield db, tmp_path
    db.close()


def test_scheduler_deduplicates_active_catalog_but_allows_discovery(runtime):
    db, _ = runtime
    first = enqueue(db, 'inventory', 'test')
    second = enqueue(db, 'scan', 'test')
    discovery = enqueue(db, 'discover', 'test')
    assert first['created'] and not second['created'] and first['job_id'] == second['job_id']
    assert discovery['created'] and discovery['job_id'] != first['job_id']


def test_partial_migration_omits_ldxp_from_oracle_manifest(runtime, monkeypatch):
    db, _ = runtime
    monkeypatch.setenv('COLLECTOR_LDXP_ENABLED', 'false')
    result = enqueue(db, 'scan', 'test')
    job = db.get(CollectorJob, result['job_id'])
    assert all(source['connector'] != 'ldxp' for source in job.sources)


def test_uploaded_collection_publishes_without_fetching_again_and_replay_does_not_duplicate(runtime, monkeypatch):
    db, directory = runtime
    result = enqueue(db, 'inventory', 'test')
    job = db.get(CollectorJob, result['job_id'])
    job.status = 'collected'
    job.result_file = job.id + '-result.jsonl.gz'
    record = {'token': 'test-shop', 'product_name': 'ChatGPT Plus 月卡 独享', 'product_url': 'https://wzyp.cn/item/abc',
              'shop_url': 'https://wzyp.cn/shop/test-shop', 'shop_name': 'Test shop', 'product_key': 'abc',
              'listed_price': '80', 'currency': 'CNY', 'stock_count': 1, 'product_status': 'in_stock',
              'source_platform': 'ldxp', 'observed_at': datetime.now(timezone.utc).isoformat()}
    lines = [{'type': 'header', 'schema': SCHEMA, 'job_id': job.id}, {'type':'source','index':0,**job.sources[0]},
             {'type':'record','record':record}, {'type':'end','status':'ok','count':1}, {'type':'complete','sources':1}]
    (directory/job.result_file).write_bytes(gzip.compress(('\n'.join(json.dumps(x) for x in lines)+'\n').encode()))
    db.commit()
    def no_fetch(*args):
        pytest.fail('publisher must not fetch external data')
    monkeypatch.setitem(CONNECTORS, 'ldxp', no_fetch)
    published = publish_ready(db, directory, release="test")
    assert published['published'] and db.get(CollectorJob, job.id).status == 'published'
    assert not publish_ready(db, directory, release="test")['published']
    assert len(list(db.scalars(select(CatalogSnapshot)))) == 1


def test_retry_exhaustion_frees_lane_for_a_new_batch(runtime):
    db, _ = runtime
    first = enqueue(db, 'inventory', 'test')
    job = db.get(CollectorJob, first['job_id'])
    job.status='running'
    job.attempts=5
    job.lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    db.commit()
    second=enqueue(db,'inventory','test')
    assert second['created'] and first['job_id'] != second['job_id']


def test_new_release_retires_queued_old_release_and_scan_is_not_starved(runtime):
    db,_=runtime
    old=enqueue(db,'inventory','old')
    new=enqueue(db,'inventory','new')
    assert new['created'] and old['job_id'] != new['job_id']
    enqueue(db,'scan','new')
    assert db.get(CollectorJob,new['job_id']).followup_kind=='scan'


def test_baseline_is_saved_before_any_remote_collection(runtime):
    db,_=runtime
    snapshot=CatalogSnapshot(published_at=datetime.now(timezone.utc))
    db.add(snapshot)
    db.commit()
    task=enqueue(db,'inventory','test')
    assert db.get(CollectorJob,task['job_id']).baseline_snapshot_id==snapshot.id


def test_missing_legacy_approval_database_prevents_migration(runtime):
    from collector_jobs import import_legacy_approvals
    db,path=runtime
    with pytest.raises(ValueError,match='approval database'):
        import_legacy_approvals(db,path/'missing.db')


def write_job_bundle(db, directory, record):
    result = enqueue(db, 'inventory', 'test')
    job = db.get(CollectorJob, result['job_id'])
    job.status, job.result_file = 'collected', job.id + '-result.jsonl.gz'
    rows = [{'type': 'header', 'schema': SCHEMA, 'job_id': job.id}, {'type': 'source', 'index': 0, **job.sources[0]},
            {'type': 'record', 'record': record}, {'type': 'end', 'status': 'ok', 'count': 1}, {'type': 'complete', 'sources': 1}]
    (directory / job.result_file).write_bytes(gzip.compress(('\n'.join(json.dumps(row) for row in rows) + '\n').encode()))
    db.commit()
    return job


def ldxp_record():
    return {'token': 'test-shop', 'product_name': 'ChatGPT Plus 月卡 独享', 'product_url': 'https://wzyp.cn/item/abc',
            'shop_url': 'https://wzyp.cn/shop/test-shop', 'source_platform': 'ldxp',
            'product_key': 'abc', 'listed_price': '80', 'stock_count':1, 'product_status':'in_stock',
            'observed_at': datetime.now(timezone.utc).isoformat()}


def test_invalid_onboarding_identity_cannot_commit_snapshot(runtime):
    db, directory = runtime
    job = write_job_bundle(db, directory, {**ldxp_record(), 'intake_id': 999, 'intake_attempt_count': 1})
    with pytest.raises(ValueError, match='onboarding identity'):
        publish_ready(db, directory, release='test')
    assert db.get(CollectorJob, job.id).status == 'failed'
    assert not list(db.scalars(select(CatalogSnapshot)))


def test_snapshot_advanced_during_collection_rejects_stale_batch(runtime):
    db, directory = runtime
    first = CatalogSnapshot(published_at=datetime.now(timezone.utc))
    db.add(first)
    db.commit()
    job = write_job_bundle(db, directory, ldxp_record())
    db.add(CatalogSnapshot(published_at=datetime.now(timezone.utc)))
    db.commit()
    with pytest.raises(RuntimeError, match='catalog changed'):
        publish_ready(db, directory, release='test')
    assert db.get(CollectorJob, job.id).status == 'failed'
    assert len(list(db.scalars(select(CatalogSnapshot)))) == 2


def test_cross_platform_collision_in_same_batch_is_rejected(runtime, tmp_path):
    from collector_jobs import validate_batch_identity
    from publish_catalog import PreparedSource, SourceSpec
    db, _ = runtime
    files = []
    for index, platform in enumerate(('ldxp', 'merchant_json')):
        path = tmp_path / str(index)
        path.write_text(json.dumps({'token': 'same', 'source_platform': platform}) + '\n')
        files.append(PreparedSource(SourceSpec('ldxp', 'ignored'), path))
    with pytest.raises(ValueError, match='conflicting shop ownership'):
        validate_batch_identity(db, files)


def test_legacy_approval_migration_is_idempotent_and_preserves_disabled_sources(runtime, monkeypatch):
    from collector_jobs import import_legacy_approvals
    from app.models import SourceIntake
    db, directory = runtime
    legacy = directory / 'legacy.db'
    legacy.touch()
    monkeypatch.setattr('collector_jobs.approved_dujiao_sources', lambda path: ['https://approved.example', 'https://disabled.example'])
    db.add(SourceIntake(source_type='dujiao_next', detected_platform='dujiao_next', source_key='https://disabled.example',
                        source_url='https://disabled.example', contact_email='', status='disabled'))
    db.commit()
    config = directory / 'merchant.json'
    config.write_text('["https://merchant.example/feed"]')
    assert import_legacy_approvals(db, legacy, config)['imported_approvals'] == 2
    assert import_legacy_approvals(db, legacy, config)['imported_approvals'] == 0
    result = enqueue(db, 'scan', 'test')
    job = db.get(CollectorJob, result['job_id'])
    assert len(job.sources) == 3
    assert all(spec['intake_ids'] for spec in job.sources if spec['connector'] != 'ldxp')
    assert not any('disabled.example' in spec['source'] for spec in job.sources)


def test_onboarding_outage_does_not_hold_catalog_lane(runtime, monkeypatch):
    db, directory = runtime
    job = write_job_bundle(db, directory, ldxp_record())
    monkeypatch.setattr('collector_jobs.finish_onboarding', lambda *args: [{'error':'temporary API outage'}])
    assert publish_ready(db, directory, release='test')['published']
    assert job.error == 'onboarding_pending'
    assert enqueue(db, 'scan', 'test')['created']


def test_recover_committed_snapshot_reconstructs_price_drop_from_baseline(runtime, monkeypatch):
    import export_alerts
    db, directory = runtime
    first = write_job_bundle(db, directory, ldxp_record())
    publish_ready(db, directory, release='test')
    second = write_job_bundle(db, directory, {**ldxp_record(), 'listed_price':'70'})
    original = export_alerts.export_snapshot_alerts
    def fail(*args, **kwargs):
        raise OSError('report volume interrupted after snapshot commit')
    monkeypatch.setattr(export_alerts, 'export_snapshot_alerts', fail)
    with pytest.raises(Exception, match='export'):
        publish_ready(db, directory, release='test')
    monkeypatch.setattr(export_alerts, 'export_snapshot_alerts', original)
    assert publish_ready(db, directory, release='test')['recovered_snapshot'] == second.published_snapshot_id
    report = json.loads((directory / 'public' / 'alerts-latest.json').read_text(encoding='utf-8'))
    assert len(report['drops']) == 1


def test_onboarding_retry_uses_saved_counts_after_a_new_snapshot(runtime, monkeypatch):
    from collector_jobs import retry_onboarding
    from app.models import SourceIntake
    db, directory = runtime
    intake = SourceIntake(source_type='ldxp', source_key='test-shop', source_url='https://wzyp.cn/shop/test-shop',
                          contact_email='', status='validated', attempt_count=1)
    db.add(intake)
    db.commit()
    calls = []
    fail = [True]
    def onboard(counts, attempts, **kwargs):
        if counts:
            calls.append(dict(counts))
        return [{'error':'temporary outage'}] if counts and fail[0] else []
    monkeypatch.setattr('ldxp_intake.onboard_published_intakes', onboard)
    first = write_job_bundle(db, directory, {**ldxp_record(), 'intake_id':intake.id, 'intake_attempt_count':1})
    publish_ready(db, directory, release='test')
    write_job_bundle(db, directory, ldxp_record())
    publish_ready(db, directory, release='test')
    first.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    fail[0] = False
    retry_onboarding(db, directory)
    assert calls == [{intake.id:1}, {intake.id:1}]
    assert first.error == ''
