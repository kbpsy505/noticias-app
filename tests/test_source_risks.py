"""Pruebas de regresión de los riesgos corregidos (antes xfail)."""
from pathlib import Path
import inspect
import re
import pytest
import actualizar
import resultados
import tipocambio
import criptoprecios

ROOT = Path(actualizar.__file__).resolve().parent
WF = ROOT / ".github" / "workflows" / "actualizar.yml"
APP_JS = ROOT / "app.js"
INDEX = ROOT / "index.html"


def test_innerhtml_in_js_is_only_used_to_clear():
    """No hay innerHTML con datos del feed; solo se vacían contenedores."""
    src = APP_JS.read_text(encoding="utf-8")
    assignments = re.findall(r"\.innerHTML\s*=\s*([^;]+)", src)
    assert assignments, "se esperaba algún innerHTML (para vaciar)"
    for expr in assignments:
        assert expr.strip() in {'""', "''", "``"}, expr


def test_headlines_go_through_textcontent_helper():
    src = APP_JS.read_text(encoding="utf-8")
    assert "e.textContent = text" in src
    assert "function el(" in src


def test_js_validates_href_schemes():
    src = APP_JS.read_text(encoding="utf-8")
    assert re.search(r"function\s+(safeHttps?Url|isSafeHttpUrl|allowedHref)", src)


def test_index_has_csp():
    html = INDEX.read_text(encoding="utf-8")
    assert "Content-Security-Policy" in html


def test_gzip_decompress_has_a_size_cap():
    src = inspect.getsource(actualizar.fetch)
    assert "gzip.decompress" not in src and "gunzip_capped" in src
    src = inspect.getsource(actualizar.gunzip_capped)
    assert "len(out) > limit" in src and "decompress(data, limit + 1)" in src


def test_curl_fallback_has_a_size_cap():
    # fetch_feed envuelve a _fetch_feed (índice de titulares para enlaces de Google Noticias)
    src = inspect.getsource(getattr(actualizar, "_fetch_feed", actualizar.fetch_feed))
    assert "curl" in src
    assert re.search(r"(max-filesize|head -c|stdout\[:|len\(data\))", src)


def test_json_helpers_cap_download_size():
    blobs = [
        inspect.getsource(resultados),
        inspect.getsource(tipocambio),
        inspect.getsource(criptoprecios),
    ]
    for src in blobs:
        assert "r.read()" not in src and re.search(r"r\.read\(\s*\d", src)


def test_json_write_is_atomic():
    src = inspect.getsource(actualizar.main)
    # Se espera write a un temporal y replace/rename sobre OUT.
    assert "replace" in src or "os.replace" in src or "rename" in src
    assert "write_text" not in src or "tmp" in src.lower()


def test_workflow_has_concurrency_group():
    yml = WF.read_text(encoding="utf-8")
    assert "concurrency:" in yml
    assert "cancel-in-progress: false" in yml
    assert "timeout-minutes: 15" in yml


def test_github_actions_are_pinned_to_sha():
    yml = WF.read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s*(\S+)", yml)
    assert uses
    for ref in uses:
        # owner/repo@<40 hex>
        assert re.search(r"@[0-9a-f]{40}$", ref), ref


def test_workflow_fallback_does_not_soft_reset():
    yml = WF.read_text(encoding="utf-8")
    assert "reset --soft" not in yml
    assert "-X theirs" not in yml


def test_gzip_bomb_is_rejected():
    import gzip
    bomb = gzip.compress(b"\0" * (actualizar.MAX_DECOMPRESSED + 10))
    with pytest.raises(ValueError):
        actualizar.gunzip_capped(bomb)
    assert actualizar.gunzip_capped(gzip.compress(b"<rss/>")) == b"<rss/>"


def test_workflow_runs_tests_before_generating():
    yml = WF.read_text(encoding="utf-8")
    assert yml.index("run_tests.sh") < yml.index("python actualizar.py")


def test_workflow_default_permissions_are_read_only():
    yml = WF.read_text(encoding="utf-8")
    top = yml.split("jobs:")[0]
    assert "contents: read" in top and "contents: write" not in top


def test_atomic_write_refuses_invalid_payload(tmp_path):
    out = tmp_path / "noticias.json"
    out.write_text('{"ok": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        actualizar.write_json_atomic(out, {"updatedAt": "x", "categories": []})
    assert out.read_text(encoding="utf-8") == '{"ok": 1}'
    bad_url = {"updatedAt": "x", "categories": [{"id": "a", "stories": [{"sources": [{"url": "http:javascript:1"}]}]}]}
    with pytest.raises(ValueError):
        actualizar.write_json_atomic(out, bad_url)
    good = {"updatedAt": "x", "categories": [{"id": "a", "stories": []}]}
    actualizar.write_json_atomic(out, good)
    import json
    assert json.loads(out.read_text(encoding="utf-8")) == good
    assert not (tmp_path / "noticias.json.tmp").exists()


def test_index_csp_allows_what_the_page_loads():
    html = INDEX.read_text(encoding="utf-8")
    assert "script-src 'self'" in html and "unsafe-eval" not in html
    assert "https://site.api.espn.com" in html  # marcadores en vivo
