import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import CollectorJob
from app.routers import collectors
from app.services.collector_protocol import SCHEMA, parse_bundle

KEY = "collector-test-key-that-is-independent-123456"
SOURCE = {"connector": "16688", "source": "https://www.16688.com.cn/shop/S1", "intake_ids": [], "shop_token": "16688-S1"}


def bundle(job_id, *, token="16688-S1", complete=True):
    record = {"token": token, "source_platform": "16688", "product_name": "ChatGPT Plus",
              "product_url": "https://www.16688.com.cn/goods/G1", "shop_url": SOURCE["source"],
              "observed_at": datetime.now(timezone.utc).isoformat(), "listed_price": "80", "product_key": "16688:G1"}
    rows = [{"type": "header", "schema": SCHEMA, "job_id": job_id}, {"type": "source", "index": 0, **SOURCE},
            {"type": "record", "record": record}, {"type": "end", "count": 1, "status": "ok"}]
    if complete:
        rows.append({"type": "complete", "sources": 1})
    return gzip.compress(("\n".join(json.dumps(row) for row in rows) + "\n").encode())


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(collectors, "SessionLocal", factory)
    settings = get_settings()
    monkeypatch.setattr(settings, "collector_enabled", True)
    monkeypatch.setattr(settings, "collector_worker_key", KEY)
    monkeypatch.setattr(settings, "collector_results_dir", str(tmp_path))
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    identity = str(uuid4())
    with factory() as db:
        db.add(CollectorJob(id=identity, kind="scan", release="test-release", active_lane="catalog", sources=[SOURCE]))
        db.commit()
    try:
        yield TestClient(app), factory, identity, tmp_path
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def claim(client, release="test-release"):
    return client.post('/api/v1/internal/collectors/claim', headers={"X-Collector-Worker-Key": KEY}, json={"worker_id": "oracle-1", "release": release})


def test_auth_version_fencing_and_exclusive_lease(runtime):
    client, factory, identity, _ = runtime
    assert client.post('/api/v1/internal/collectors/claim', json={"worker_id": "bad", "release": "test-release"}).status_code == 401
    assert claim(client, "wrong-release").json() is None
    first = claim(client).json()
    assert first['id'] == identity
    assert claim(client).json() is None
    with factory() as db:
        db.get(CollectorJob, identity).lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    second = claim(client).json()
    assert second['token'] != first['token'] and second['attempt'] == 2
    assert client.post(f'/api/v1/internal/collectors/{identity}/heartbeat', headers={"X-Collector-Worker-Key": KEY}, json={"token": first['token']}).status_code == 409


def test_complete_result_is_durable_idempotent_and_contains_no_secrets(runtime):
    client, factory, identity, directory = runtime
    task = claim(client).json()
    headers = {"X-Collector-Worker-Key": KEY, "X-Collector-Lease": task['token']}
    response = client.put(f'/api/v1/internal/collectors/{identity}/result', headers=headers, content=bundle(identity))
    assert response.status_code == 200
    with factory() as db:
        job = db.get(CollectorJob, identity)
        assert job.status == 'collected' and (directory / job.result_file).is_file()
    assert client.put(f'/api/v1/internal/collectors/{identity}/result', headers=headers, content=b'').json()['already_received']
    assert len(list(directory.glob('*.gz'))) == 1


@pytest.mark.parametrize('options', [{'token': '16688-S2'}, {'complete': False}])
def test_bad_result_never_becomes_publishable_and_removes_temporary_upload(runtime, options):
    client, factory, identity, directory = runtime
    task = claim(client).json()
    response = client.put(f'/api/v1/internal/collectors/{identity}/result',
        headers={"X-Collector-Worker-Key": KEY, "X-Collector-Lease": task['token']}, content=bundle(identity, **options))
    assert response.status_code == 422
    with factory() as db:
        assert db.get(CollectorJob, identity).status == 'running'
    assert not list(directory.glob('*.gz'))


def test_protocol_rejects_oversized_lines_and_wrong_job(tmp_path):
    path = tmp_path / 'input.gz'
    path.write_bytes(bundle(str(uuid4())))
    with pytest.raises(ValueError, match='identity'):
        parse_bundle(path, str(uuid4()), [SOURCE], tmp_path / 'rows')


def test_failure_revokes_lease_immediately(runtime):
    client,factory,identity,_=runtime
    task=claim(client).json()
    headers={"X-Collector-Worker-Key":KEY}
    assert client.post(f'/api/v1/internal/collectors/{identity}/failure',headers=headers,
        json={"token":task['token'],"error":"connection dropped"}).status_code==200
    assert client.post(f'/api/v1/internal/collectors/{identity}/heartbeat',headers=headers,
        json={"token":task['token']}).status_code==409
    assert claim(client).json() is None


def test_non_ascii_or_wrong_source_identity_is_rejected(runtime):
    client,_,identity,_=runtime
    assert client.post(f'/api/v1/internal/collectors/{identity}/heartbeat',headers={"X-Collector-Worker-Key":KEY},
        json={"token":"中"*48}).status_code==422
    from app.services.collector_protocol import validate_collected_record
    source={"connector":"16688","source":"https://www.16688.com.cn/shop/S1"}
    row={"token":"16688-S2","source_platform":"16688","shop_url":"https://www.16688.com.cn/shop/S2",
         "product_name":"Plus","product_url":"https://www.16688.com.cn/goods/G1","observed_at":datetime.now(timezone.utc).isoformat()}
    with pytest.raises(ValueError,match='identity'):
        validate_collected_record(row,source)


def test_hosted_merchant_feed_keeps_its_feed_identity_and_public_shop_domain():
    from app.services.collector_protocol import validate_collected_record
    import hashlib
    url='https://feeds.example/catalog.json'
    row={"token":"merchant-json-"+hashlib.sha256(url.encode()).hexdigest()[:24],"source_platform":"merchant_json",
         "shop_url":"https://store.example","product_url":"https://store.example/plus","product_name":"Plus",
         "observed_at":datetime.now(timezone.utc).isoformat()}
    validate_collected_record(row,{"connector":"merchant-json","source":url})
    row['product_url']='https://169.254.169.254/latest/meta-data'
    with pytest.raises(ValueError):
        validate_collected_record(row,{"connector":"merchant-json","source":url})


def test_production_collector_key_must_not_equal_admin():
    from app.core.runtime_safety import validate_api_runtime_settings
    from app.core.config import Settings
    settings=Settings(app_env='production',collector_enabled=True,collector_worker_key='a'*32,admin_api_key='a'*32,
        intake_worker_key='b'*32,detector_worker_key='c'*32,discovery_worker_key='d'*32,
        session_secret_key='e'*32,bot_secret_encryption_key='f'*32,public_site_url='https://example.com',
        web_origin='https://example.com',api_docs_enabled=False)
    with pytest.raises(RuntimeError,match='distinct'):validate_api_runtime_settings(settings)


@pytest.mark.parametrize('changes', [
    {'shop_url': 'https://www.16688.com.cn/shop/S2'},
    {'product_url': 'https://other.example/goods/G1'},
    {'product_url': 'https://www.16688.com.cn/shop/S2'},
    {'product_key': 'x' * 301},
    {'stock_count': 2147483648},
    {'raw_json': {'untrusted_number': float('nan')}},
    {'shop_name': 'bad\x00name'},
])
def test_verified_token_cannot_authorize_different_links_or_oversized_keys(changes):
    from app.services.collector_protocol import validate_collected_record
    row = json.loads(gzip.decompress(bundle('test')).splitlines()[2])['record']
    with pytest.raises(ValueError):
        validate_collected_record({**row, **changes}, SOURCE)


def test_deterministic_feed_identity_ignores_unrelated_origin_match():
    from app.services.collector_protocol import validate_collected_record
    import hashlib
    source = 'https://feeds.example:443/second.json'
    canonical = 'https://feeds.example/second.json'
    row = {'token': 'merchant-json-' + hashlib.sha256(canonical.encode()).hexdigest()[:24],
           'source_platform': 'merchant_json', 'shop_url': 'https://shop.example',
           'product_url': 'https://shop.example/plus', 'product_name': 'Plus',
           'observed_at': datetime.now(timezone.utc).isoformat()}
    validate_collected_record(row, {'connector': 'merchant-json', 'source': source, 'shop_token': 'wrong-origin-match'})


def test_browser_identity_accepts_existing_case_and_safe_http_display_links():
    from app.services.collector_protocol import validate_collected_record
    row = {'token':'AI16888','shop_url':'https://wzyp.cn/shop/ai16888','product_url':'http://wzyp.cn/item/1',
           'product_name':'Plus','source_platform':'ldxp','observed_at':datetime.now(timezone.utc).isoformat()}
    validate_collected_record(row, {'connector':'ldxp','source':'/data/ldxp_crawler.db'})
    row['product_url'] = 'http://169.254.169.254/latest'
    with pytest.raises(ValueError):
        validate_collected_record(row, {'connector':'ldxp','source':'/data/ldxp_crawler.db'})


def test_uncertain_database_commit_preserves_accepted_upload(runtime, monkeypatch):
    from contextlib import contextmanager
    from sqlalchemy.exc import OperationalError
    client, factory, identity, directory = runtime
    task = claim(client).json()
    failed = []
    @contextmanager
    def connection():
        with factory() as db:
            original = db.commit
            def commit():
                accepting = any(isinstance(row, CollectorJob) and row.status == 'collected' for row in db.identity_map.values())
                original()
                if accepting and not failed:
                    failed.append(True)
                    raise OperationalError('COMMIT', {}, ConnectionError('confirmation lost'))
            db.commit = commit
            yield db
    monkeypatch.setattr(collectors, 'SessionLocal', connection)
    headers = {'X-Collector-Worker-Key': KEY, 'X-Collector-Lease': task['token']}
    with pytest.raises(OperationalError):
        client.put(f'/api/v1/internal/collectors/{identity}/result', headers=headers, content=bundle(identity))
    with factory() as db:
        job = db.get(CollectorJob, identity)
        assert job.status == 'collected' and (directory / job.result_file).is_file()
    assert client.put(f'/api/v1/internal/collectors/{identity}/result', headers=headers, content=b'').json()['already_received']
