from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from connectors import kmdian
from connectors.base import SourceFetchError
from price_radar_http import PinnedHTTPSClient, PinnedResponse


def product(goods_no="KM07826776", shop_code="S825584", **changes):
    # Field names and units verified against the live platform API.
    return {
        "shop_name": "测试店铺",
        "shop_url": f"https://www.kmdian.com/shop/{shop_code}",
        "shop_code": shop_code,
        "goods_no": goods_no,
        "title": "ChatGPT Plus 直充一个月",
        "product_url": f"https://www.kmdian.com/item/{goods_no}",
        "price_cent": 2750,
        "stock": 999999,
        "sales_count": 7,
        "cover": "https://img.kmdian.com/test.webp",
        "updated_at": "2026-01-01T00:00:00+08:00",
        **changes,
    }


def page(items, *, current=1, per_page=20, total=None):
    total = len(items) if total is None else total
    return {
        "code": 0, "message": "ok",
        "data": {
            "list": items,
            "pagination": {"page": current, "per_page": per_page, "total": total,
                           "last_page": max(1, (total + per_page - 1) // per_page)},
        },
    }


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv(kmdian.API_KEY_ENV, "test-app.test-secret")
    state = SimpleNamespace(responses=[], calls=[], now=0.0, products={}, detail_override=None)

    def sleep(seconds):
        state.now += seconds

    monkeypatch.setattr(kmdian, "time", SimpleNamespace(monotonic=lambda: state.now, time=lambda: state.now, sleep=sleep))

    class Client:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

        def __init__(self, **_kwargs):
            pass

        def get(self, url, *, accept, headers=None):
            state.calls.append((url, accept, headers, state.now))
            if '/api/v1/products/' in url:
                source = state.products[url.rsplit('/', 1)[-1]]
                response = state.detail_override or {'code':0,'data':{'product':{'goods_no':source['goods_no'],'description':'<p>公开商品说明</p>'},'shop':{'shop_code':source['shop_code']}}}
            else:
                response = state.responses.pop(0)
                if isinstance(response, dict):
                    for item in response.get('data', {}).get('list', []):
                        state.products[item.get('goods_no')] = item
            if isinstance(response, Exception):
                raise response
            if isinstance(response, PinnedResponse):
                return response
            return PinnedResponse(200, {"content-type": "application/json"}, json.dumps(response).encode())

    monkeypatch.setattr(kmdian, "PinnedHTTPSClient", Client)
    return state


def test_paginated_platform_feed_preserves_shop_identity_prices_inventory_and_sales(api, monkeypatch):
    monkeypatch.setattr(kmdian, "PAGE_SIZE", 2)
    api.responses = [
        page([product(), product("KM2", "S2", stock=0, price_cent=1)], per_page=2, total=3),
        page([product("KM3", stock=None, price_cent=0)], current=2, per_page=2, total=3),
        page([product(), product("KM2", "S2", stock=0, price_cent=1)], per_page=2, total=3),
        page([product("KM3", stock=None, price_cent=0)], current=2, per_page=2, total=3),
    ]
    records = list(kmdian.load_records(kmdian.API_URL))
    assert len(records) == 3
    assert {row["token"] for row in records} == {"kmdian-S825584", "kmdian-S2"}
    assert [row["listed_price"] for row in records] == [Decimal("27.50"), Decimal("0.01"), Decimal("0.00")]
    assert [row["product_status"] for row in records] == ["in_stock", "out_of_stock", "unknown"]
    assert records[0]["raw_json"] == {**product(), 'description':'<p>公开商品说明</p>', 'description_images':[]}
    assert records[0]["observed_at"].tzinfo is not None
    assert records[0]["observed_at"] <= records[1]["observed_at"]
    assert all(row["source_platform"] == "kmdian" and row["source_kind"] == "platform_api" for row in records)
    assert records[0]["shop_url"] == product()["shop_url"]
    assert records[0]["product_url"] == product()["product_url"]
    assert [parse_qs(urlsplit(call[0]).query)["page"] for call in api.calls[:4]] == [["1"], ["2"], ["1"], ["2"]]
    assert all(call[2] == {"X-Api-Key": "test-app.test-secret"} for call in api.calls[:4])
    assert all(call[2] is None for call in api.calls[4:])
    assert api.calls[1][3] - api.calls[0][3] > 1.0
    assert "test-secret" not in str(records)


@pytest.mark.parametrize("source", ["https://evil.example/products", kmdian.API_URL + "?page=2", "http://www.kmdian.com/api/v1/open/products"])
def test_credential_never_goes_to_another_endpoint(api, source):
    with pytest.raises(ValueError, match="source must be"):
        list(kmdian.load_records(source))
    assert api.calls == []


def test_key_is_required_before_network_access(api, monkeypatch):
    monkeypatch.delenv(kmdian.API_KEY_ENV)
    with pytest.raises(ValueError, match="KMDIAN_API_KEY is required"):
        list(kmdian.load_records(kmdian.API_URL))
    assert api.calls == []


@pytest.mark.parametrize("status, error, message", [
    (401, ValueError, "access denied"), (403, ValueError, "IP whitelist"),
    (408, SourceFetchError, "request timeout"), (429, SourceFetchError, "rate limit"),
    (503, SourceFetchError, "HTTP 503"),
])
def test_access_and_transient_errors_are_explicit_and_do_not_leak_credentials(api, status, error, message):
    api.responses = [PinnedResponse(status, {}, b'{"message":"test-app.test-secret"}')]
    with pytest.raises(error, match=message) as caught:
        list(kmdian.load_records(kmdian.API_URL))
    assert "test-secret" not in str(caught.value)
    assert len(api.calls) == 1


@pytest.mark.parametrize("document", [
    {"code": 0, "data": {}}, {"code": 21003, "message": "test-app.test-secret"},
    page([product(price_cent=-1)]), page([product(price_cent=27.5)]),
    page([product(price_cent=True)]), page([product(product_url="javascript:alert(1)")]),
    page([product(diagnostic="test-app.test-secret")]),
    page([product()], total=2),
])
def test_malformed_or_partial_data_is_not_accepted_as_a_complete_catalog(api, document):
    api.responses = [document]
    with pytest.raises(ValueError) as caught:
        list(kmdian.load_records(kmdian.API_URL))
    assert "test-secret" not in str(caught.value)


@pytest.mark.parametrize("second", [
    page([product()], current=2, per_page=1, total=2),
    page([product("KM2")], current=1, per_page=1, total=2),
    page([product("KM2")], current=2, per_page=1, total=3),
])
def test_repeated_products_pages_or_changing_totals_abort_the_import(api, monkeypatch, second):
    monkeypatch.setattr(kmdian, "PAGE_SIZE", 1)
    api.responses = [page([product()], per_page=1, total=2), second]
    with pytest.raises(ValueError):
        list(kmdian.load_records(kmdian.API_URL))


def test_empty_platform_catalog_is_valid(api):
    api.responses = [page([])]
    assert list(kmdian.load_records(kmdian.API_URL)) == []


def test_detail_retains_text_images_and_excludes_untrusted_image_urls(api):
    api.responses = [page([product()])]
    api.detail_override = {'code':0,'data':{'product':{'goods_no':'KM07826776',
        'description':'<p>说明</p><img src="https://img.kmdian.com/detail.jpg"><img src="https://[bad"><img src="javascript:alert(1)"><img src="https://img.kmdian.com.evil.test/x">',
        'usage_note':'使用说明'},'shop':{'shop_code':'S825584'},'category_name':'AI 账号'}}
    row = list(kmdian.load_records(kmdian.API_URL))[0]
    assert row['raw_json']['description_images'] == ['https://img.kmdian.com/detail.jpg']
    assert row['raw_json']['description'].endswith('使用说明')
    assert row['category_name'] == 'AI 账号'
    assert api.calls[-1][2] is None


@pytest.mark.parametrize('override', [
    PinnedResponse(503, {}, b'error'),
    {'code':0,'data':{'product':{'goods_no':'OTHER'},'shop':{'shop_code':'S825584'}}},
    {'code':0,'data':{'product':{'goods_no':'KM07826776'},'shop':{'shop_code':'OTHER'}}},
])
def test_detail_failure_or_wrong_identity_never_publishes_partial_catalog(api, override):
    api.responses = [page([product()])]
    api.detail_override = override
    with pytest.raises((ValueError, SourceFetchError)):
        list(kmdian.load_records(kmdian.API_URL))


def test_detail_cache_resumes_bounded_work_and_refreshes_changed_items(api, monkeypatch, tmp_path):
    monkeypatch.setenv('COLLECTOR_RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(kmdian,'MAX_TASK_SECONDS',23)
    api.responses=[page([product(),product('KM2')])]
    with pytest.raises(SourceFetchError,match='budget reached'):
        list(kmdian.load_records(kmdian.API_URL))
    assert (tmp_path/'kmdian-details'/'KM07826776.json').is_file()
    api.calls.clear();api.responses=[page([product(),product('KM2')])]
    monkeypatch.setattr(kmdian,'MAX_TASK_SECONDS',100)
    assert len(list(kmdian.load_records(kmdian.API_URL)))==2
    assert [url.rsplit('/',1)[-1] for url,_,_,_ in api.calls if '/api/v1/products/' in url]==['KM2']
    api.calls.clear();api.responses=[page([product(updated_at='2026-11-25T16:00:00+08:00')])]
    list(kmdian.load_records(kmdian.API_URL))
    assert len(api.calls)==2


@pytest.mark.parametrize('value',[False,0,[],{}])
def test_invalid_detail_text_is_not_coerced_to_empty(api, value):
    api.responses=[page([product()])]
    api.detail_override={'code':0,'data':{'product':{'goods_no':'KM07826776','description':value},'shop':{'shop_code':'S825584'}}}
    with pytest.raises(ValueError,match='content is invalid'):list(kmdian.load_records(kmdian.API_URL))


def test_html_encoded_credential_never_reaches_public_description_or_images(api):
    api.responses=[page([product()])]
    encoded=''.join('&#'+str(ord(c))+';' for c in 'test-app.test-secret')
    api.detail_override={'code':0,'data':{'product':{'goods_no':'KM07826776',
        'description':'<p>'+encoded+'</p><img src="https://img.kmdian.com/'+encoded+'">'},'shop':{'shop_code':'S825584'}}}
    with pytest.raises(ValueError,match='credential'):list(kmdian.load_records(kmdian.API_URL))


@pytest.mark.parametrize('field,value', [('description','test-app.<script>ignored</script>test-secret'),
    ('category_name','test-app.test-&#115;ecret')])
def test_final_visible_text_including_category_cannot_reveal_key(api, field, value):
    api.responses=[page([product()])]
    data={'product':{'goods_no':'KM07826776'},'shop':{'shop_code':'S825584'}}
    (data if field=='category_name' else data['product'])[field]=value
    api.detail_override={'code':0,'data':data}
    with pytest.raises(ValueError,match='credential'):list(kmdian.load_records(kmdian.API_URL))


def test_unfinished_detail_cache_survives_normal_refresh_ttl(api, monkeypatch, tmp_path):
    monkeypatch.setenv('COLLECTOR_RESULTS_DIR',str(tmp_path))
    monkeypatch.setattr(kmdian,'MAX_TASK_SECONDS',23)
    api.responses=[page([product(),product('KM2')])]
    with pytest.raises(SourceFetchError):list(kmdian.load_records(kmdian.API_URL))
    api.now += 10*3600
    api.calls.clear();api.responses=[page([product(),product('KM2')])]
    monkeypatch.setattr(kmdian,'MAX_TASK_SECONDS',100)
    assert len(list(kmdian.load_records(kmdian.API_URL)))==2
    assert [url.rsplit('/',1)[-1] for url,_,_,_ in api.calls if '/api/v1/products/' in url]==['KM2']


def test_removed_product_details_are_pruned_from_private_cache(api, monkeypatch, tmp_path):
    monkeypatch.setenv('COLLECTOR_RESULTS_DIR',str(tmp_path))
    api.responses=[page([product()])]
    list(kmdian.load_records(kmdian.API_URL))
    cached=tmp_path/'kmdian-details'/'KM07826776.json';assert cached.exists()
    api.responses=[page([])]
    assert list(kmdian.load_records(kmdian.API_URL))==[]
    assert not cached.exists()


def test_server_clamped_page_size_still_requires_a_confirming_pass(api):
    # The server may return fewer than the requested 20 items per page.
    pages = [
        page([product()], per_page=1, total=2),
        page([product("KM2")], current=2, per_page=1, total=2),
    ]
    api.responses = pages + pages
    assert len(list(kmdian.load_records(kmdian.API_URL))) == 2
    assert len(api.calls) == 6


def test_equal_totals_with_changed_product_membership_abort(api):
    api.responses = [
        page([product()], per_page=1, total=2),
        page([product("KM2")], current=2, per_page=1, total=2),
        page([product("KM2")], per_page=1, total=2),
        page([product("KM3")], current=2, per_page=1, total=2),
    ]
    with pytest.raises(ValueError, match="catalog changed"):
        list(kmdian.load_records(kmdian.API_URL))


def test_unknown_raw_fields_are_discarded_and_nested_values_rejected(api):
    api.responses = [page([product(diagnostic={"unexpected": "value"})])]
    assert "diagnostic" not in list(kmdian.load_records(kmdian.API_URL))[0]["raw_json"]
    api.responses = [page([product(cover={"url": "https://example.com/image"})])]
    with pytest.raises(ValueError, match="cover must be a string"):
        list(kmdian.load_records(kmdian.API_URL))


def test_network_failure_does_not_echo_exception_credentials(api):
    api.responses = [TimeoutError("test-app.test-secret")]
    with pytest.raises(SourceFetchError) as caught:
        list(kmdian.load_records(kmdian.API_URL))
    assert "test-secret" not in str(caught.value)


def test_credential_echo_is_rejected_even_when_json_escapes_the_key(api, monkeypatch):
    key = 'test-app.sec"ret'
    monkeypatch.setenv(kmdian.API_KEY_ENV, key)
    api.responses = [page([product(title=key)])]
    with pytest.raises(ValueError, match="response contains the API credential") as caught:
        list(kmdian.load_records(kmdian.API_URL))
    assert key not in str(caught.value)
