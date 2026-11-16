from urllib.parse import urlparse
import pytest
from actualizar import clean_url


def test_strips_tracking_query_and_fragment():
    u = clean_url("https://www.example.com/nota?utm_source=x&id=1#section")
    assert u == "https://www.example.com/nota?id=1"


def test_javascript_scheme_is_dropped_by_http_prefix_rule():
    u = clean_url("javascript:alert(1)")
    assert not u.startswith("http")


def test_data_and_file_schemes_are_dropped_by_http_prefix_rule():
    assert not clean_url("data:text/html,<h1>x</h1>").startswith("http")
    assert not clean_url("file:///etc/passwd").startswith("http")


def test_protocol_relative_is_dropped():
    assert not clean_url("//evil.example/path").startswith("http")


def _strict_http(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in {"http", "https"} and bool(p.netloc)


def test_http_javascript_bypass_is_rejected():
    from actualizar import is_safe_http_url
    assert is_safe_http_url(clean_url("http:javascript:alert(1)")) is False


def test_https_without_netloc_is_rejected():
    from actualizar import is_safe_http_url
    assert is_safe_http_url(clean_url("https:evil")) is False


@pytest.mark.parametrize("u", ["javascript:alert(1)", "data:text/html,x", "file:///etc/passwd",
                               "//evil.example/x", "ftp://example.com/x", "", "http://"])
def test_is_safe_http_url_rejects(u):
    from actualizar import is_safe_http_url
    assert is_safe_http_url(u) is False


def test_is_safe_http_url_accepts_normal_links():
    from actualizar import is_safe_http_url
    assert is_safe_http_url("https://www.nacion.com/el-pais/nota/")
    assert is_safe_http_url("http://example.com/a?b=1")
