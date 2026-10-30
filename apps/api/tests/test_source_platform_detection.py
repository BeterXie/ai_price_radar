import hashlib

from app.services.source_platform import _ldxp_detection, prepare_source_submission


def test_submission_preserves_catfk_host_and_scopes_merchant_identity():
    result = prepare_source_submission("https://CATFK.com/shop/I8WO6J9O/?ref=public")
    official = prepare_source_submission("https://wzyp.cn/shop/I8WO6J9O")
    assert result.platform == "unknown"
    assert result.source_url == "https://catfk.com/shop/I8WO6J9O"
    assert result.source_key == "catfk:i8wo6j9o"
    assert result.shop_token == "catfk:I8WO6J9O"
    assert result.source_key != official.source_key
    assert result.shop_token != official.shop_token
    detected = _ldxp_detection(result.source_url)
    assert detected is not None
    assert detected.platform == "ldxp"
    assert detected.source_url == result.source_url
    assert detected.source_key == result.source_key


def test_catfk_long_token_identity_fits_shop_storage():
    token = "A" * 128
    result = prepare_source_submission(f"https://catfk.com/shop/{token}")
    expected = "catfk:sha256:" + hashlib.sha256(token.casefold().encode()).hexdigest()
    assert result.shop_token == result.source_key == expected
    assert len(result.shop_token) <= 128
    assert result.source_url == f"https://catfk.com/shop/{token}"
    assert prepare_source_submission(f"https://catfk.com/shop/{token.lower()}").source_key == expected


def test_catfk_alias_detection_does_not_rewrite_unverified_hosts_or_ports():
    assert _ldxp_detection("https://catfk.com.example/shop/I8WO6J9O") is None
    assert _ldxp_detection("https://catfk.com:8443/shop/I8WO6J9O") is None


def test_submission_normalizes_ldxp_identity():
    result = prepare_source_submission("https://pay.ldxp.cn/shop/ABC123")
    assert result.platform == "unknown"
    assert result.source_key == "abc123"
    assert result.source_url == "https://pay.ldxp.cn/shop/ABC123"
    assert result.shop_token == "ABC123"


def test_submission_normalizes_wzyp_identity():
    result = prepare_source_submission("https://wzyp.cn/shop/KFLA")
    assert result.platform == "unknown"
    assert result.source_key == "kfla"
    assert result.source_url == "https://wzyp.cn/shop/KFLA"
    assert result.shop_token == "KFLA"


def test_submission_scopes_16688_token():
    result = prepare_source_submission("https://www.16688.com.cn/shop/HARVEY")
    assert result.platform == "unknown"
    assert result.source_url == result.source_key == "https://www.16688.com.cn/shop/HARVEY"
    assert result.shop_token == "16688-HARVEY"


def test_submission_preserves_unverified_source_url():
    result = prepare_source_submission("https://shop.example.com:8443/ai-price-radar.json")
    assert result.platform == "unknown"
    assert result.source_url == result.source_key == "https://shop.example.com:8443/ai-price-radar.json"
