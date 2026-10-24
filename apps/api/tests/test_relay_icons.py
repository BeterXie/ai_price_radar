import base64
import threading

import pytest
from price_radar_http import PinnedResponse

from app.services import relay_icons

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=")
HOME = "https://relay.example.com/"


@pytest.fixture(autouse=True)
def isolated_icons():
    relay_icons._cache.clear()
    yield
    relay_icons._cache.clear()


def install_client(monkeypatch, responses):
    calls = []
    limits = {}

    class Client:
        def __init__(self, **kwargs):
            limits.update(kwargs)

        @staticmethod
        def normalize_url(url):
            return original.normalize_url(url)

        def get(self, url, *, accept):
            calls.append(url)
            result = responses.get(url, PinnedResponse(404, {}, b""))
            if isinstance(result, Exception):
                raise result
            return result

    original = relay_icons.PinnedHTTPSClient
    monkeypatch.setattr(relay_icons, "PinnedHTTPSClient", Client)
    return calls, limits


def html(body):
    return PinnedResponse(200, {"content-type": "text/html; charset=utf-8"}, body.encode())


def test_declared_icon_uses_public_homepage_and_is_cached(monkeypatch):
    calls, limits = install_client(monkeypatch, {
        HOME: html('<link rel="shortcut icon" href="/assets/brand.png">'),
        HOME + "assets/brand.png": PinnedResponse(200, {}, PNG),
    })
    icon = relay_icons.get_relay_icon(HOME + "register?invite=private")
    assert icon == relay_icons.RelayIcon(PNG, "image/png")
    assert relay_icons.get_relay_icon(HOME + "login") == icon
    assert calls == [HOME, HOME + "assets/brand.png"]
    assert limits["max_response_bytes"] == 256 * 1024
    assert limits["max_task_seconds"] == 8
    assert limits["request_timeout"] == 2


@pytest.mark.parametrize("website", ["http://relay.example.com", "https://127.0.0.1", "https://relay.local", "https://user:pass@relay.example.com", "https://relay.example.com:8443"])
def test_unsafe_homepage_never_reaches_network(monkeypatch, website):
    calls, _ = install_client(monkeypatch, {})
    assert relay_icons.get_relay_icon(website) is None
    assert calls == []


def test_unsafe_declared_links_and_svg_fall_back_to_favicon(monkeypatch):
    calls, _ = install_client(monkeypatch, {
        HOME: html('<link rel="icon" href="http://internal/secret"><link rel="icon" href="https://127.0.0.1/private"><link rel="icon" href="data:image/png;base64,abc"><link rel="icon" type="image/svg+xml" href="/logo.svg">'),
        HOME + "favicon.ico": PinnedResponse(200, {}, PNG),
    })
    assert relay_icons.get_relay_icon(HOME).media_type == "image/png"
    assert calls == [HOME, HOME + "favicon.ico"]


def test_relative_icon_respects_first_html_base(monkeypatch):
    calls, _ = install_client(monkeypatch, {
        HOME: html('<base href="/assets/"><base href="/ignored/"><link rel="icon" href="brand.png">'),
        HOME + "assets/brand.png": PinnedResponse(200, {}, PNG),
    })
    assert relay_icons.get_relay_icon(HOME).body == PNG
    assert calls == [HOME, HOME + "assets/brand.png"]


@pytest.mark.parametrize("base", ["https://127.0.0.1/", "http://internal/"])
def test_unsafe_html_base_cannot_send_relative_icon_requests_to_internal_hosts(monkeypatch, base):
    calls, _ = install_client(monkeypatch, {
        HOME: html(f'<base href="{base}"><link rel="icon" href="private.png">'),
        HOME + "favicon.ico": PinnedResponse(200, {}, PNG),
    })
    assert relay_icons.get_relay_icon(HOME).body == PNG
    assert calls == [HOME, HOME + "favicon.ico"]


def test_homepage_redirect_is_not_followed_but_favicon_is_still_tried(monkeypatch):
    calls, _ = install_client(monkeypatch, {
        HOME: ValueError("source redirects are not followed"),
        HOME + "favicon.ico": PinnedResponse(200, {}, PNG),
    })
    assert relay_icons.get_relay_icon(HOME) is not None
    assert calls == [HOME, HOME + "favicon.ico"]


def test_malformed_html_declaration_still_uses_favicon_and_caches_result(monkeypatch):
    calls, _ = install_client(monkeypatch, {
        HOME: html("<![bogus]>"),
        HOME + "favicon.ico": PinnedResponse(200, {}, PNG),
    })
    assert relay_icons.get_relay_icon(HOME).body == PNG
    assert relay_icons.get_relay_icon(HOME).body == PNG
    assert calls == [HOME, HOME + "favicon.ico"]


@pytest.mark.parametrize("body", [b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', b"<html>not an image</html>", PNG + b"x" * (256 * 1024)], ids=["svg", "html", "oversized"])
def test_invalid_or_oversized_images_are_not_served_and_failure_is_cached(monkeypatch, body):
    calls, _ = install_client(monkeypatch, {HOME + "favicon.ico": PinnedResponse(200, {"content-type": "image/png"}, body)})
    assert relay_icons.get_relay_icon(HOME) is None
    assert relay_icons.get_relay_icon(HOME) is None
    assert calls == [HOME, HOME + "favicon.ico"]


def test_declared_candidates_are_bounded_and_duplicate_links_do_not_spend_requests(monkeypatch):
    calls, _ = install_client(monkeypatch, {
        HOME: html(''.join(f'<link rel="icon" href="/icon{i}.png">' for i in [1, 1, 2, 3, 4])),
        HOME + "favicon.ico": PinnedResponse(200, {}, PNG),
    })
    assert relay_icons.get_relay_icon(HOME) is not None
    assert calls == [HOME, HOME + "icon1.png", HOME + "icon2.png", HOME + "favicon.ico"]


def test_cache_expires_and_evicts_old_entries(monkeypatch):
    now = [100.0]
    fetched = []
    monkeypatch.setattr(relay_icons.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(relay_icons, "_MAX_CACHE_ENTRIES", 2)
    monkeypatch.setattr(relay_icons, "_fetch_icon", lambda url: fetched.append(url))
    for url in [HOME, "https://two.example.com", "https://three.example.com", HOME]:
        assert relay_icons.get_relay_icon(url) is None
    assert fetched.count(HOME) == 2
    now[0] += 15 * 60 + 1
    assert relay_icons.get_relay_icon(HOME) is None
    assert fetched.count(HOME) == 3


def test_concurrent_duplicate_requests_do_not_repeat_external_fetch(monkeypatch):
    started, finish = threading.Event(), threading.Event()
    fetched = []
    results = []

    def fetch(url):
        fetched.append(url)
        started.set()
        assert finish.wait(2)
        return relay_icons.RelayIcon(PNG, "image/png")

    monkeypatch.setattr(relay_icons, "_fetch_icon", fetch)
    def request():
        results.append(relay_icons.get_relay_icon(HOME))

    thread = threading.Thread(target=request)
    duplicate = threading.Thread(target=request)
    thread.start()
    try:
        assert started.wait(2)
        duplicate.start()
        assert fetched == [HOME]
    finally:
        finish.set()
        thread.join(3)
        duplicate.join(3)
    assert not thread.is_alive()
    assert not duplicate.is_alive()
    assert results == [relay_icons.RelayIcon(PNG, "image/png")] * 2
    assert relay_icons.get_relay_icon(HOME).body == PNG


def test_capacity_exhaustion_is_transient_and_not_negative_cached(monkeypatch):
    class BusySlots:
        def acquire(self, *, timeout):
            assert timeout == 8
            return False

    monkeypatch.setattr(relay_icons, "_slots", BusySlots())
    with pytest.raises(relay_icons.RelayIconBusy):
        relay_icons.get_relay_icon(HOME)
    assert HOME not in relay_icons._cache
    assert HOME not in relay_icons._in_flight
