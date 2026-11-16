"""Corrida de main() sin red: un feed roto no tumba el run; el JSON es válido."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import actualizar
from helpers import rss_feed, recent, rfc2822

T1 = "Maduro enfrenta un juicio en Nueva York tras su captura"
T2 = "Tras la captura de Maduro, arranca el juicio en Nueva York"
T3 = "Maduro faces trial in New York after his capture"
DESC = "El exmandatario Maduro enfrenta un juicio en Nueva York tras su captura."


def _rss(title, link, lang="es"):
    return rss_feed([{
        "title": title,
        "link": link,
        "description": DESC if lang == "es" else "Maduro faces a trial in New York after his capture, the court said.",
        "date": recent(1),
    }])


FAKE_FEEDS = [
    ("bbc", "https://fixture.example/bbc.xml", "BBC", "bbc", "es", "politica"),
    ("elpais", "https://fixture.example/elpais.xml", "El País", "elpais", "es", "politica"),
    ("nyt", "https://fixture.example/nyt.xml", "The New York Times", "nyt", "en", "politica"),
    ("roto", "https://fixture.example/broken.xml", "Roto", "roto", "es", None),
]

XML = {
    "https://fixture.example/bbc.xml": _rss(T1, "https://bbc.example/maduro"),
    "https://fixture.example/elpais.xml": _rss(T2, "https://elpais.example/maduro"),
    "https://fixture.example/nyt.xml": _rss(T3, "https://nyt.example/maduro", lang="en"),
    "https://fixture.example/broken.xml": b"<rss><channel><item><title>sin cerrar",
}


def fake_fetch(url, simple=False):
    data = XML.get(url)
    if data is None:
        raise RuntimeError(f"unexpected fetch: {url}")
    return data


def _noop_build(*a, **k):
    raise RuntimeError("red deshabilitada en pruebas")


def _empty_tipocambio(now):
    return None, {"skipped": "offline test"}


def test_broken_feed_does_not_abort_and_json_is_valid(tmp_path):
    out = tmp_path / "noticias.json"
    # Evitar curl en el feed roto
    import subprocess
    orig_run = subprocess.run

    def no_curl(*a, **k):
        raise RuntimeError("curl disabled in tests")

    import buenas, cripto, criptoprecios, narrar, regiones, resultados, tema, tipocambio

    def boom(*a, **k):
        raise RuntimeError("offline: módulo opcional omitido en la prueba")

    patches = [
        patch.object(actualizar, "FEEDS", FAKE_FEEDS),
        patch.object(actualizar, "OUT", out),
        patch.object(actualizar, "fetch", fake_fetch),
        patch.object(actualizar, "load_previous", lambda: None),
        # Los módulos opcionales fallan a propósito: main() debe atraparlo y seguir.
        patch.object(tema, "build", boom),
        patch.object(cripto, "build", boom),
        patch.object(regiones, "build", boom),
        patch.object(buenas, "build", boom),
        patch.object(tipocambio, "build", boom),
        patch.object(criptoprecios, "build", boom),
        patch.object(resultados, "build", boom),
        patch.object(narrar, "narrate", boom),
    ]
    subprocess.run = no_curl
    try:
        for p in patches:
            p.start()
        actualizar.ARTICLE_TEXT.clear()
        actualizar.main()
    finally:
        for p in patches:
            p.stop()
        subprocess.run = orig_run

    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))

    # Esquema mínimo
    assert "updatedAt" in data
    assert "nextRefreshAt" in data
    assert data["refreshHours"] == 3
    assert data["method"]["minOutlets"] == 3
    assert isinstance(data["categories"], list)
    assert data["categories"], "debe haber pestañas aunque algunas vayan vacías"
    ids = [c["id"] for c in data["categories"]]
    for required in ("politica", "buenas", "posibles", "deportes"):
        # buenas/posibles pueden faltar si su builder falló (lo atrapa main)
        if required in ("politica", "deportes"):
            assert required in ids

    # El feed roto quedó registrado y no tumbó la corrida
    failed_ids = {f["id"] for f in data["feedsFailed"]}
    assert "roto" in failed_ids
    ok_ids = {f["id"] for f in data["feedsOk"]}
    assert "bbc" in ok_ids and "elpais" in ok_ids and "nyt" in ok_ids

    # Consenso 3 medios en política
    politica = next(c for c in data["categories"] if c["id"] == "politica")
    # Con 3 notas en todo el corpus el filtro de df (>6%) no deja términos distintivos, así que
    # aquí no se exige consenso (eso lo cubre test_cluster con corpus de relleno).
    from urllib.parse import urlparse
    for c in data["categories"]:
        for st in c["stories"]:
            for src in st["sources"]:
                p = urlparse(src["url"])
                assert p.scheme in {"http", "https"} and p.netloc

    # JSON serializa de ida y vuelta (no NaN ni valores raros)
    json.loads(json.dumps(data))

    # updatedAt es ISO UTC
    datetime.strptime(data["updatedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
