import importlib.util
import json
from pathlib import Path
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'apps/api/app/services'), str(ROOT/'shared_http'), str(ROOT/'collector')]


@pytest.fixture
def worker(tmp_path, monkeypatch):
    key=tmp_path/'key'
    key.write_text('test-collector-key')
    monkeypatch.setenv('COLLECTOR_API_URL','http://127.0.0.1:18081')
    monkeypatch.setenv('COLLECTOR_RELEASE','test')
    monkeypatch.setenv('COLLECTOR_KEY_FILE',str(key))
    monkeypatch.setenv('COLLECTOR_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(Path,'read_text',_mock_config(Path.read_text))
    spec=importlib.util.spec_from_file_location('collector_worker_test',ROOT/'collector/worker.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mock_config(original):
    def read(path,*args,**kwargs):
        if path.name=='collection-keywords.json' and not path.exists():
            return original(ROOT/'config/collection-keywords.json',*args,**kwargs)
        return original(path,*args,**kwargs)
    return read


def test_worker_rejects_local_files_or_manifest_changes_before_collection(worker, monkeypatch):
    from uuid import uuid4
    job={'id':str(uuid4()),'release':'test','kind':'scan','token':'x',
         'sources':[{'connector':'merchant-json','source':'/etc/passwd'}]}
    with pytest.raises(ValueError):
        worker.collect(job,threading.Event())


@pytest.mark.parametrize('bundle_age,expected_fetches', [(0, 1), (3700, 2)])
def test_completed_sources_survive_failed_upload_and_are_not_refetched(worker, monkeypatch, bundle_age, expected_fetches):
    import os
    import time
    from datetime import datetime,timezone
    from uuid import uuid4
    from collector_protocol import parse_bundle
    job={'id':str(uuid4()),'release':'test','kind':'scan','token':'x',
         'sources':[{'connector':'16688','source':'https://www.16688.com.cn/shop/S1','intake_ids':[]}]}
    calls=[]
    monkeypatch.setattr(worker,'scan',lambda *args:None)
    def load(source):
        calls.append(source)
        yield {'token':'16688-S1','shop_url':source,'source_platform':'16688','product_name':'Team 5x','product_url':'https://www.16688.com.cn/goods/G1','product_key':'16688:G1'}
    monkeypatch.setattr(worker,'get_connector',lambda name:load)
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def put(self,*args,**kwargs):raise ConnectionError('upload disconnected')
    monkeypatch.setattr(worker.httpx,'Client',Client)
    with pytest.raises(ConnectionError):worker.collect(job,threading.Event())
    # A long scan may finish after its first source checkpoints expire. Retry
    # the complete bundle, keeping all original observation times intact.
    directory=worker.DATA/'jobs'/job['id']
    checkpoint=directory/'0.status.json'
    os.utime(checkpoint, (time.time()-3700, time.time()-3700))
    completed=(directory/'result.jsonl.gz').read_bytes()
    if bundle_age:
        os.utime(directory/'result.jsonl.gz', (time.time()-bundle_age, time.time()-bundle_age))
    with pytest.raises(ConnectionError):worker.collect(job,threading.Event())
    assert len(calls)==expected_fetches
    path=worker.DATA/'jobs'/job['id']/'result.jsonl.gz'
    if not bundle_age:
        assert path.read_bytes()==completed
    result=parse_bundle(path,job['id'],job['sources'],worker.DATA/'decoded')
    assert result[0]['count']==1


def test_failed_source_discards_partial_records(worker, monkeypatch):
    from uuid import uuid4
    import gzip
    job={'id':str(uuid4()),'release':'test','kind':'scan','token':'x','sources':[{'connector':'16688','source':'https://www.16688.com.cn/shop/S1'}]}
    monkeypatch.setattr(worker,'scan',lambda *args:None)
    def broken(source):
        yield {'token':'16688-S1','shop_url':source,'source_platform':'16688','product_name':'Team','product_url':'https://www.16688.com.cn/goods/G1','product_key':'16688:G1'}
        raise OSError('timeout')
    monkeypatch.setattr(worker,'get_connector',lambda _:broken)
    class Response:
        def raise_for_status(self):pass
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def put(self,*args,**kwargs):return Response()
    monkeypatch.setattr(worker.httpx,'Client',Client)
    worker.collect(job,threading.Event())
    path=worker.DATA/'jobs'/job['id']/'result.jsonl.gz'
    rows=[json.loads(line) for line in gzip.open(path,'rt')]
    assert not any(row['type']=='record' for row in rows)
    assert next(row for row in rows if row['type']=='end')['status']=='fetch_failed'


def test_hourly_jobs_reuse_16688_without_refetching_or_retimestamping(worker, monkeypatch):
    import gzip
    import time
    from datetime import datetime,timezone
    from uuid import uuid4
    now=[time.time()]
    stamp=datetime.now(timezone.utc).isoformat()
    monkeypatch.setenv('COLLECTOR_16688_CACHE','true')
    monkeypatch.setattr(worker.source_cache.time,'time',lambda:now[0])
    calls=[];observed=[]
    source='https://www.16688.com.cn/shop/S1'
    def records(url):
        calls.append(url)
        yield {'token':'16688-S1','shop_url':url,'source_platform':'16688','product_name':'ChatGPT Plus',
               'product_url':'https://www.16688.com.cn/goods/G1','product_key':'16688:G1','observed_at':stamp}
    def deliver(job,bundle,lost):
        rows=[json.loads(line) for line in gzip.open(bundle,'rt')]
        observed.append(next(row['record']['observed_at'] for row in rows if row['type']=='record'))
    monkeypatch.setattr(worker,'get_connector',lambda _:records)
    monkeypatch.setattr(worker,'deliver_bundle',deliver)
    for elapsed in (0,3600,6*3600):
        now[0]+=elapsed
        worker.collect({'id':str(uuid4()),'release':'test','kind':'scan','token':'x',
                        'sources':[{'connector':'16688','source':source}]},threading.Event())
    assert len(calls)==2
    assert observed==[stamp,stamp,stamp]


def test_capacity_failure_aborts_batch_instead_of_publishing_empty_source(worker, monkeypatch):
    from uuid import uuid4
    job = {'id': str(uuid4()), 'release': 'test', 'kind': 'scan', 'token': 'x',
           'sources': [{'connector': '16688', 'source': 'https://www.16688.com.cn/shop/S1'}]}
    monkeypatch.setattr(worker, 'scan', lambda *args: None)
    monkeypatch.setattr(worker, 'MAX_LINE', 64)
    monkeypatch.setattr(worker, 'get_connector', lambda _: lambda source: iter([{
        'token': '16688-S1', 'shop_url': source, 'source_platform': '16688',
        'product_name': 'Team', 'product_url': 'https://www.16688.com.cn/goods/G1', 'product_key':'16688:G1'}]))
    with pytest.raises(worker.CollectionCapacityError):
        worker.collect(job, threading.Event())
    assert not (worker.DATA / 'jobs' / job['id'] / '0.status.json').exists()


def test_partial_discovery_does_not_skip_browser_discovery(worker, monkeypatch):
    calls = []
    def command(args, lost, **kwargs):
        calls.append(args[2])
        return {'failures': {'normalize': 2, 'bing': 1}}
    monkeypatch.setattr(worker, 'run_command', command)
    worker.discover(threading.Event())
    assert calls == ['discover-sources', 'discover']


def test_non_ldxp_batch_does_not_require_browser_scan(worker, monkeypatch):
    from uuid import uuid4
    job={'id':str(uuid4()),'release':'test','kind':'scan','token':'x',
         'sources':[{'connector':'16688','source':'https://www.16688.com.cn/shop/S1','shop_token':'16688-S1'}]}
    called=[]
    monkeypatch.setattr(worker,'scan',lambda *args: called.append(True))
    def load(source):
        yield {'token':'16688-S1','shop_url':source,'source_platform':'16688','product_name':'Team',
               'product_url':'https://www.16688.com.cn/goods/G1','product_key':'16688:G1'}
    monkeypatch.setattr(worker,'get_connector',lambda name:load)
    class Response:
        def raise_for_status(self):pass
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def put(self,*args,**kwargs):return Response()
    monkeypatch.setattr(worker.httpx,'Client',Client)
    worker.collect(job,threading.Event())
    assert called == []


def test_disabled_browser_rejects_old_ldxp_manifest_before_any_io(worker, monkeypatch):
    from uuid import uuid4
    monkeypatch.setenv('COLLECTOR_LDXP_ENABLED','false')
    job={'id':str(uuid4()),'release':'test','kind':'scan','token':'x','sources':[{'connector':'ldxp','source':'/data/ldxp_crawler.db'}]}
    with pytest.raises(worker.TaskPolicyError):worker.collect(job,threading.Event())
    assert not (worker.DATA/'jobs'/job['id']).exists()
