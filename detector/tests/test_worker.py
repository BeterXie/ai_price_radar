import signal
import time

import pytest

import worker
from qualify import QualificationResult


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="production detector runs on Linux")
def test_probe_timeout_includes_blocking_resolver_time(monkeypatch):
    monkeypatch.setattr(worker, "probe_source", lambda _url: time.sleep(1))
    started_at = time.monotonic()
    with pytest.raises(TimeoutError, match="total time limit"):
        worker._probe_with_timeout("https://slow.example", timeout_seconds=0.01)
    assert time.monotonic() - started_at < 0.5


def test_run_once_claims_and_reports_candidate_tasks(monkeypatch):
    requests: list[tuple[str, dict]] = []

    def fake_request(path: str, payload: dict, **kwargs):
        requests.append((path, payload))
        if path.endswith("/source-detections/claim"):
            return []
        if path.endswith("/source-candidates/claim"):
            return [{
                "candidate_id": 7,
                "canonical_url": "https://woo.example.com/products/chatgpt",
                "platform_hint": "unknown",
                "attempt_count": 2,
                "lease_expires_at": "2099-01-01T00:00:00+00:00",
            }]
        if path.endswith("/source-candidates/7/result"):
            return {"candidate_id": 7, "status": "promoted"}
        return {}

    monkeypatch.setattr(worker, "DISCOVERY_WORKER_KEY", "discovery-test")
    monkeypatch.setattr(worker, "_request", fake_request)
    monkeypatch.setattr(
        worker,
        "qualify_candidate",
        lambda url, hint: QualificationResult(
            status="detected",
            detected_platform="woocommerce",
            detected_source_key="https://woo.example.com",
            detected_source_url="https://woo.example.com",
            total_product_count=1,
            ai_product_count=1,
            sample_products=[{"name": "ChatGPT Plus", "url": "https://woo.example.com/p/1"}],
            fingerprints=["woocommerce-store-api"],
            confidence_score=88,
        ),
    )
    processed = worker.run_once()
    assert processed == 1
    claim_call = next(item for item in requests if item[0].endswith("/source-candidates/claim"))
    assert claim_call[1] == {"limit": 5, "lease_seconds": 900, "scope": "all"}
    result_call = next(item for item in requests if item[0].endswith("/source-candidates/7/result"))
    assert result_call[1]["attempt_count"] == 2
    assert result_call[1]["status"] in {"detected", "no_match", "validation_failed"}


def test_oracle_worker_claims_one_scoped_intake_and_defers_pacing_without_failure(monkeypatch):
    from price_radar_http.pacing import OriginCoolingDown
    calls=[]
    monkeypatch.setattr(worker,'DETECTOR_SCOPE','16688')
    monkeypatch.setattr(worker,'WORKER_KEY','test')
    monkeypatch.setattr(worker,'DISCOVERY_WORKER_KEY','')
    def request(path,payload,**kwargs):
        calls.append((path,payload))
        return [{'intake_id':805,'source_url':'https://www.16688.com.cn/shop/XIAOMO','attempt_count':2}]
    monkeypatch.setattr(worker,'_request',request)
    def busy(url):raise OriginCoolingDown('16688 pacing busy')
    monkeypatch.setattr(worker,'_probe_with_timeout',busy)
    assert worker.run_once()==0
    assert calls==[('/api/v1/internal/source-detections/claim',{'limit':1,'lease_seconds':300,'scope':'16688'})]


def test_wrong_scope_is_rejected_before_any_probe(monkeypatch):
    monkeypatch.setattr(worker,'DETECTOR_SCOPE','other')
    monkeypatch.setattr(worker,'WORKER_KEY','test')
    monkeypatch.setattr(worker,'DISCOVERY_WORKER_KEY','')
    monkeypatch.setattr(worker,'_request',lambda *a,**kw:[{'intake_id':805,'source_url':'https://www.16688.com.cn/shop/XIAOMO'}])
    monkeypatch.setattr(worker,'_probe_with_timeout',lambda url:pytest.fail('main detector must not contact 16688'))
    assert worker.run_once()==0


def test_scope_matches_idna_and_unsupported_port_routing():
    assert worker.is_16688('https://ｗｗｗ.１６６８８.com.cn/shop/XIAOMO')
    assert worker.is_16688('https://www.16688.com.cn:443/shop/XIAOMO')
    assert not worker.is_16688('https://www.16688.com.cn:8443/shop/XIAOMO')
    assert not worker.is_16688('https://www.16688.com.cn.evil.example/shop/XIAOMO')


def test_oracle_candidate_qualification_receives_full_network_budget(monkeypatch):
    monkeypatch.setattr(worker,'DETECTOR_SCOPE','16688')
    monkeypatch.setattr(worker,'WORKER_KEY','')
    monkeypatch.setattr(worker,'DISCOVERY_WORKER_KEY','test')
    calls=[]
    def request(path,payload,**kwargs):
        if path.endswith('/claim'):
            assert payload['scope']=='16688' and payload['limit']==1
            return [{'candidate_id':1,'canonical_url':'https://16688.com.cn/shop/S1','platform_hint':'unknown','attempt_count':1}]
        calls.append(payload)
        return {}
    monkeypatch.setattr(worker,'_request',request)
    def qualify(url,hint,*,client):
        assert 59 < client.deadline-time.monotonic() <= 60 and client.request_timeout==20
        return QualificationResult('no_match','16688',url,url,0,0,[],[],90)
    monkeypatch.setattr(worker,'qualify_candidate',qualify)
    assert worker.run_once()==1
    assert calls[0]['status']=='no_match'


def test_rejected_result_does_not_abandon_other_claims(monkeypatch):
    from urllib.error import HTTPError
    from probe import ProbeResult
    calls=[]
    monkeypatch.setattr(worker,'DETECTOR_SCOPE','all')
    monkeypatch.setattr(worker,'WORKER_KEY','test')
    monkeypatch.setattr(worker,'DISCOVERY_WORKER_KEY','')
    monkeypatch.setattr(worker,'_probe_with_timeout',lambda url:ProbeResult('ldxp',url,url,'long-name'*30,1))
    def request(path,payload,**kwargs):
        calls.append((path,payload))
        if path.endswith('/claim'):
            return [{'intake_id':i,'source_url':f'https://ldxp.cn/shop/{i}','attempt_count':1} for i in (1,2)]
        if '/1/result' in path:raise HTTPError(path,422,'stale',None,None)
        return {'status':'approved'}
    monkeypatch.setattr(worker,'_request',request)
    assert worker.run_once()==1
    assert calls[-1][0].endswith('/2/result')
    assert len(calls[-1][1]['shop_name'])==120
