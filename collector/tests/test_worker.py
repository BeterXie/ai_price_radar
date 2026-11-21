import importlib.util
import json
from pathlib import Path
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'apps/api/app/services'), str(ROOT/'shared_http')]


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


def test_completed_sources_survive_failed_upload_and_are_not_refetched(worker, monkeypatch):
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
    for _ in range(2):
        with pytest.raises(ConnectionError):worker.collect(job,threading.Event())
    assert len(calls)==1
    path=worker.DATA/'jobs'/job['id']/'result.jsonl.gz'
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
