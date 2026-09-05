from app.services.source_platform import prepare_source_submission


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
