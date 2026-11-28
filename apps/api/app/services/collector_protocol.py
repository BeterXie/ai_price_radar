"""Versioned, bounded collector records; shared by API, publisher and worker."""
from __future__ import annotations

import gzip
import json
import hashlib
import re
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from price_radar_http import PinnedHTTPSClient
from price_radar_http.platform_16688 import HOSTS, canonical_url as canonical_16688_url

SCHEMA = "pricememo.collection.v1"
MAX_COMPRESSED = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_LINE = 2 * 1024 * 1024
MAX_RECORDS = 250_000
CONNECTORS = {"ldxp", "16688", "dujiao-next", "merchant-json", "woocommerce-store", "schema-org", "acg-faka"}


def validate_collected_record(record: dict, spec: dict) -> None:
    if not isinstance(record, dict) or any(not isinstance(record.get(key), str) or not record[key].strip()
                                         for key in ("token", "product_name", "product_url", "shop_url")):
        raise ValueError("invalid collected record")
    def finite_json(value):
        if isinstance(value, dict):
            for key, item in value.items():
                finite_json(key)
                finite_json(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                finite_json(item)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError('non-finite collection value')
        elif isinstance(value, str) and '\x00' in value:
            raise ValueError('NUL is not valid catalog text')
    finite_json(record)
    if isinstance(record.get('raw_json'), str):
        try:
            raw = json.loads(record['raw_json'])
        except ValueError:
            raw = None
        finite_json(raw)
    for field in ('stock_count', 'source_score', 'consecutive_failures'):
        value = record.get(field)
        if value not in (None, ''):
            try:
                number = int(float(value)) if field == 'stock_count' else int(value)
            except (TypeError, ValueError):
                if field == 'stock_count':
                    continue  # Existing importer treats unparseable stock as unknown.
                raise ValueError('invalid integer collection field')
            except OverflowError as exc:
                raise ValueError('collection integer exceeds storage limit') from exc
            if not -2147483648 <= number <= 2147483647:
                raise ValueError('collection integer exceeds storage limit')
    connector = spec["connector"]
    platform = {"woocommerce-store": "woocommerce"}.get(connector, connector.replace("-", "_"))
    if record.get("source_platform") != platform:
        raise ValueError("collected platform mismatch")
    def display_url(value):
        # Browser-collected HTTP links are display data, never request targets.
        checked = 'https://' + value[7:] if connector == 'ldxp' and value.startswith('http://') else value
        normalized = PinnedHTTPSClient.normalize_url(checked)
        return canonical_16688_url(normalized) if connector == '16688' else normalized
    shop_url = display_url(record["shop_url"])
    product = urlsplit(display_url(record["product_url"]))
    shop = urlsplit(shop_url)
    source = urlsplit(display_url(spec["source"])) if connector != "ldxp" else None
    if connector not in {"ldxp", "merchant-json"} and shop.hostname != source.hostname:
        raise ValueError("collected shop origin mismatch")
    expected = spec.get("shop_token")
    if connector == "ldxp":
        if shop.hostname not in {"ldxp.cn","pay.ldxp.cn","www.ldxp.cn","wzyp.cn","www.wzyp.cn","catfk.com"}:
            raise ValueError("unexpected LDXP shop host")
        match = re.fullmatch(r"/shop/([A-Za-z0-9._~-]{1,128})/?", shop.path)
        if not match:
            raise ValueError("invalid LDXP shop identity")
        expected = match[1]
        if shop.hostname == "catfk.com":
            original_product = urlsplit(record['product_url'])
            if original_product.scheme != 'https' or original_product.hostname != 'catfk.com':
                raise ValueError('catfk product origin mismatch')
            expected = "catfk:" + expected
            if len(expected) > 128:
                expected = "catfk:sha256:" + hashlib.sha256(match[1].casefold().encode()).hexdigest()
    elif connector == "16688":
        if '#' in record['shop_url'] or '#' in record['product_url']:
            raise ValueError("16688 links must not contain fragments")
        if source.hostname not in HOSTS:
            raise ValueError("invalid 16688 source origin")
        match = re.fullmatch(r"/shop/([A-Za-z0-9._~-]{1,128})/?", source.path)
        expected = expected or ("16688-" + match[1] if match else None)
        if not expected or not expected.startswith("16688-"):
            raise ValueError("16688 source requires a verified shop identity")
        if shop.path != "/shop/" + expected.removeprefix("16688-") or shop.query or shop.fragment:
            raise ValueError("16688 shop identity mismatch")
        if product.netloc != source.netloc or not re.fullmatch(r"/goods/[A-Za-z0-9._~-]{1,128}", product.path) or product.query or product.fragment:
            raise ValueError("16688 goods identity mismatch")
        if record.get('product_key') != '16688:' + product.path.removeprefix('/goods/'):
            raise ValueError("16688 product key mismatch")
    else:
        if connector != 'merchant-json' and (shop.path not in ('', '/') or shop.query or '#' in record['shop_url']):
            raise ValueError('collected shop must use its canonical root URL')
        # Reproduce the existing connector identities, never invent a second key.
        origin = f"https://{source.hostname if connector == 'acg-faka' else source.netloc}"
        lengths = {"dujiao-next":20,"woocommerce-store":20,"schema-org":20,"acg-faka":24}
        if connector in lengths:
            expected = connector + "-" + hashlib.sha256(origin.encode()).hexdigest()[:lengths[connector]]
        elif connector == "merchant-json":
            expected = "merchant-json-" + hashlib.sha256(PinnedHTTPSClient.normalize_url(spec["source"]).encode()).hexdigest()[:24]
        if connector in {"dujiao-next", "schema-org", "acg-faka"} and product.netloc != source.netloc:
            raise ValueError("collected product origin mismatch")
        if connector == 'acg-faka' and (not re.fullmatch(r'/item/[0-9]+', product.path) or str(record.get('product_key')) != product.path.removeprefix('/item/')):
            raise ValueError("ACG-Faka product key mismatch")
    matches = expected.casefold() == record['token'].casefold() if connector == 'ldxp' else expected == record['token']
    if not matches:
        raise ValueError("collected shop identity mismatch")
    if connector != 'ldxp':
        record['shop_url'] = shop_url
        record['product_url'] = product.geturl()
    key = str(record.get("product_key") or record.get("source_product_key") or record["product_url"]).strip()
    if len(record["token"]) > 128 or not key or len(key) > 300:
        raise ValueError("collected identity exceeds storage limit")
    if record.get("intake_id") is not None:
        if connector != "ldxp" or type(record["intake_id"]) is not int or record["intake_id"] <= 0:
            raise ValueError("invalid intake identity")
        if type(record.get("intake_attempt_count")) is not int or record["intake_attempt_count"] <= 0:
            raise ValueError("invalid intake attempt")
    stamp = record.get("observed_at") or record.get("collected_at")
    parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("invalid collection timestamp")


def parse_bundle(path: Path, job_id: str, sources: list[dict], output_dir: Path) -> list[dict]:
    """No archive extraction or sender-controlled filesystem paths."""
    if path.stat().st_size > MAX_COMPRESSED:
        raise ValueError("compressed collection exceeds limit")
    output_dir.mkdir(parents=True, exist_ok=True)
    total = count = 0
    results = []
    stream = None
    source_index = -1
    source_count = 0
    done = False
    try:
        with gzip.open(path, "rb") as data:
            while True:
                line = data.readline(MAX_LINE + 1)
                if not line:
                    break
                total += len(line)
                if len(line) > MAX_LINE or total > MAX_EXPANDED:
                    raise ValueError("collection data exceeds limit")
                row = json.loads(line)
                if done or not isinstance(row, dict):
                    raise ValueError("invalid collection framing")
                kind = row.get("type")
                if kind == "header" and source_index == -1 and not results and stream is None:
                    if row.get("schema") != SCHEMA or row.get("job_id") != job_id:
                        raise ValueError("collection identity mismatch")
                    source_index = 0
                elif kind == "source" and stream is None and source_index == len(results) and source_index < len(sources):
                    expected = sources[source_index]
                    if row.get("index") != source_index or row.get("connector") != expected["connector"] or row.get("source") != expected["source"]:
                        raise ValueError("collection source mismatch")
                    stream = (output_dir / f"{source_index}.jsonl").open("w", encoding="utf-8")
                    source_count = 0
                elif kind == "record" and stream is not None:
                    record = row.get("record")
                    validate_collected_record(record, sources[source_index])
                    source_count += 1
                    count += 1
                    if count > MAX_RECORDS:
                        raise ValueError("too many collected records")
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                elif kind == "end" and stream is not None:
                    if row.get("count") != source_count or not isinstance(row.get("status"), str) or row.get("status") not in {"ok", "fetch_failed", "unavailable"}:
                        raise ValueError("incomplete collection source")
                    if row["status"] != "ok" and source_count:
                        raise ValueError("failed sources cannot publish partial records")
                    stream.close()
                    stream = None
                    results.append({"path": str(output_dir / f"{source_index}.jsonl"), "status": row["status"],
                                    "count": source_count, "error": str(row.get("error", ""))[:500]})
                    source_index += 1
                elif kind == "complete" and source_index >= 0 and stream is None and len(results) == len(sources) and row.get("sources") == len(sources):
                    done = True
                else:
                    raise ValueError("invalid collection order")
        if not done:
            raise ValueError("collection was interrupted")
        return results
    finally:
        if stream is not None:
            stream.close()
