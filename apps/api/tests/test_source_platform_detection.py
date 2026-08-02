from app.services.source_platform import detect_source_platform


def _public_resolver(*_args, **_kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def test_detection_recognizes_ldxp_without_fetching():
    result = detect_source_platform(
        "https://pay.ldxp.cn/shop/ABC123",
        fetch_json=lambda _url: (_ for _ in ()).throw(AssertionError("LDXP should not be fetched")),
    )
    assert result.platform == "ldxp"
    assert result.source_key == "abc123"


def test_detection_recognizes_dujiao_next_public_contract():
    def fetch(url: str):
        if url.endswith("/config"):
            return {"status_code": 0, "data": {"site_name": "Example"}}
        if "/products?" in url:
            return {"status_code": 0, "data": [], "pagination": {"page": 1, "total_page": 0}}
        raise AssertionError(url)

    result = detect_source_platform("https://shop.example.com/products/example", fetch_json=fetch, resolver=_public_resolver)
    assert result.platform == "dujiao_next"
    assert result.source_url == "https://shop.example.com"


def test_detection_recognizes_merchant_json_feed():
    def fetch(url: str):
        if "/api/v1/public/" in url:
            raise ValueError("not Dujiao")
        return {"shop": {"name": "Example"}, "items": [{"name": "ChatGPT Plus", "price": 20}]}

    result = detect_source_platform("https://shop.example.com/ai-price-radar.json", fetch_json=fetch, resolver=_public_resolver)
    assert result.platform == "merchant_json"
    assert result.source_url.endswith("/ai-price-radar.json")
