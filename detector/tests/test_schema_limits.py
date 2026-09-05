import pytest

from price_radar_http import PinnedResponse
from qualify import _jsonld_product_nodes, _price_of_product
from sitemap import product_page_urls, sitemap_locations


def test_deep_jsonld_is_a_controlled_validation_failure():
    body = b'<script type="application/ld+json">' + b"[" * 2000 + b"0" + b"]" * 2000 + b"</script>"
    with pytest.raises(ValueError, match="(nesting|node) limit"):
        _jsonld_product_nodes(body)


def test_zero_aggregate_price_is_preserved():
    assert _price_of_product({"offers": {"lowPrice": 0, "price": 12, "priceCurrency": "CNY"}}) == ("0", "CNY")


def test_sitemap_ignores_image_extensions():
    body = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://shop.example/product</loc><image:image><image:loc>https://shop.example/photo.jpg</image:loc></image:image></url></urlset>'
    assert sitemap_locations(body) == ("urlset", ["https://shop.example/product"])


def test_sitemap_rejects_error_status_before_parsing():
    with pytest.raises(ValueError, match="HTTP 503"):
        product_page_urls("https://shop.example/sitemap.xml", "https://shop.example", None, preloaded=PinnedResponse(503, {}, b"<urlset/>"))
