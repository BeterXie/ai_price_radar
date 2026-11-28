import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'shared_http'))
from price_radar_http import pacing


@pytest.mark.skipif(sys.platform=='win32',reason='Shared collection lock runs on Linux')
def test_pacing_is_shared_across_www_alias_and_blocks_without_additional_requests(tmp_path,monkeypatch):
    monkeypatch.setenv('COLLECTOR_RATE_DIR',str(tmp_path))
    now=[1000.0]
    sleeps=[]
    monkeypatch.setattr(pacing.time,'time',lambda:now[0])
    def sleep(seconds):
        sleeps.append(seconds)
        now[0]+=seconds
    monkeypatch.setattr(pacing.time,'sleep',sleep)
    with pacing.origin_budget('16688.com.cn') as result:result(200)
    with pytest.raises(pacing.OriginCoolingDown,match='520'):
        with pacing.origin_budget('www.16688.store') as result:result(520)
    assert sleeps==[2.0]
    with pytest.raises(pacing.OriginCoolingDown,match='cooling'):
        with pacing.origin_budget('www.16688.com.cn'):pytest.fail('blocked origin must not send')
    now[0]+=901
    with pacing.origin_budget('16688.store') as result:result(200)


def test_pacing_does_not_change_unconfigured_or_other_hosts(monkeypatch):
    monkeypatch.delenv('COLLECTOR_RATE_DIR',raising=False)
    with pacing.origin_budget('16688.store') as result:result(520)
    monkeypatch.setenv('COLLECTOR_RATE_DIR','invalid path that must not be accessed')
    with pacing.origin_budget('other.example') as result:result(200)
