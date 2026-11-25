import json
from pathlib import Path
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'collector'),str(ROOT/'apps/api/app/services')]
import source_cache


def test_cache_preserves_real_observation_and_expires_without_other_platforms(tmp_path,monkeypatch):
    now=[1000.0]
    monkeypatch.setattr(source_cache.time,'time',lambda:now[0])
    spec={'connector':'16688','source':'https://www.16688.com.cn/shop/S1'}
    row={'token':'16688-S1','shop_url':spec['source'],'source_platform':'16688','product_name':'ChatGPT Plus',
         'product_url':'https://www.16688.com.cn/goods/G1','product_key':'16688:G1',
         'observed_at':datetime.now(timezone.utc).isoformat()}
    records=tmp_path/'complete.jsonl';records.write_text(json.dumps(row)+'\n')
    source_cache.store(tmp_path,spec,records,1)
    now[0]+=3600
    assert source_cache.load(tmp_path,spec)==[row]
    assert source_cache.load(tmp_path,{'connector':'merchant-json','source':spec['source']}) is None
    now[0]+=5*3600
    assert source_cache.load(tmp_path,spec) is None


def test_cache_rejects_partial_and_cross_shop_data(tmp_path):
    spec={'connector':'16688','source':'https://www.16688.com.cn/shop/S1'}
    row={'token':'16688-S2','shop_url':'https://www.16688.com.cn/shop/S2','source_platform':'16688',
         'product_name':'test','product_url':'https://www.16688.com.cn/goods/G1','product_key':'16688:G1',
         'observed_at':datetime.now(timezone.utc).isoformat()}
    records=tmp_path/'complete.jsonl';records.write_text(json.dumps(row)+'\n')
    source_cache.store(tmp_path,spec,records,1)
    assert source_cache.load(tmp_path,spec) is None


def test_cache_rejects_non_object_and_deep_metadata_and_separates_goods(tmp_path):
    shop={'connector':'16688','source':'https://www.16688.com.cn/shop/S1'}
    goods={'connector':'16688','source':'https://www.16688.com.cn/goods/S1'}
    assert source_cache._path(tmp_path,shop)!=source_cache._path(tmp_path,goods)
    path=source_cache._path(tmp_path,shop);path.parent.mkdir(parents=True)
    for text in ('null\n','['*1500+'0'+']'*1500+'\n'):
        path.write_text(text)
        assert source_cache.load(tmp_path,shop) is None
    data=source_cache._path(tmp_path,shop)
    data.write_text('{broken')
    assert source_cache.load(tmp_path,shop) is None
