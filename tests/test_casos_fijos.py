"""Casos fijos del plan de mejoras de contenido (07_Noticias/03_Library/2026-11-17-plan-mejoras-contenido.md).

Datos reales recortados de noticias.json de main c620ea0 (tests/fixtures/casos_fijos.json). Sin red:
el decodificador de Google Noticias se sustituye por un diccionario.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import actualizar

# Se quitan a medida que cada fase entra (fase 0: los casos quedan escritos y fallan en main).
FASE1 = pytest.mark.xfail(not getattr(actualizar, "PHASE", 0) >= 1, reason="fase 1", strict=False)
FASE2 = pytest.mark.xfail(not getattr(actualizar, "PHASE", 0) >= 3, reason="fases 2-3", strict=False)
FASE4 = pytest.mark.xfail(not getattr(actualizar, "PHASE", 0) >= 4, reason="fase 4", strict=False)

FIX = json.loads((Path(__file__).parent / "fixtures" / "casos_fijos.json").read_text(encoding="utf-8"))
QUEPOS_GN = ("https://news.google.com/rss/articles/CBMipAFBVV95cUxQWVBXVXFyeVhaX3RLQlYxZnRwLW9PZzVIaTI3aU9SMHJNd0ZSQ0hPY3hiSlZsaTBJWl9aSDFmbTZPbzNrQk5PRkpGSTZuLXV6ZjFKaGZBVVg4dUZPcmI3bEJVSmhaOTg0ZWdBUjhNcEVFZHA5U2pXZ1BVTXZQOEIxMlpPTmM1QTIwMzBZUUtNSm43Wk8wQS1HYkgzbVZPMUdiak1kSA?oc=5")
QUEPOS_REAL = "https://observador.cr/costarricense-de-quepos-obtiene-beca-rhodes-para-investigar-el-cancer-en-oxford/"


def cats():
    return copy.deepcopy(FIX["categories"])


def cards_with(cs, word):
    return [(c["id"], s) for c in cs for s in c["stories"] if word in (s["headline"] + " " + (s.get("headlineEn") or "")).lower()]


def pipeline(cs, decoded=None, monkeypatch=None):
    """Pasos nuevos de la rama, en el orden de main(): resolver Google Noticias, deduplicar y asignar sección."""
    import enlaces
    if monkeypatch is not None:
        monkeypatch.setattr(enlaces, "_gn_decode", lambda url: (decoded or {}).get(url))
        monkeypatch.setattr(enlaces, "_state", {"decodes": 0, "streak": 0})
        enlaces.CACHE.clear()
    actualizar.resolve_story_links(cs)
    cs, _ = actualizar.final_dedup(cs)
    actualizar.assign_sections(cs)
    return cs


@FASE2
def test_quepos_una_tarjeta_en_costa_rica_con_chip_avances(monkeypatch):
    cs = pipeline(cats(), {QUEPOS_GN: QUEPOS_REAL}, monkeypatch)
    hits = cards_with(cs, "quepos")
    assert len(hits) == 1, [h[0] for h in hits]
    cid, st = hits[0]
    assert st["section"] == "costarica"
    assert any(a.get("section") == "avances" for a in st.get("alsoIn", []))
    urls = [x["url"] for x in st["sources"]]
    assert QUEPOS_REAL in urls or any("observador.cr" in u for u in urls)
    assert "news.google.com" not in st["sources"][0]["url"]


@FASE2
def test_quepos_solo_buenas_tambien_va_a_costa_rica(monkeypatch):
    """Si la nota tica solo llegó por Buenas (cr: true), igual su sección es Costa Rica con chip Avances."""
    cs = [c for c in cats() if c["id"] == "buenas"]
    cs = pipeline(cs, {QUEPOS_GN: QUEPOS_REAL}, monkeypatch)
    (cid, st), = cards_with(cs, "quepos")
    assert st["section"] == "costarica"
    assert any(a.get("section") == "avances" for a in st.get("alsoIn", []))
    assert st["sources"][0]["url"] == QUEPOS_REAL


@FASE2
def test_carney_unido(monkeypatch):
    cs = pipeline(cats(), {}, monkeypatch)
    hits = cards_with(cs, "carney")
    assert len(hits) == 1, [(h[0], h[1]["headline"]) for h in hits]
    assert hits[0][1]["outlets"] >= 6


@FASE2
def test_camilo_rodriguez_sin_copias(monkeypatch):
    cs = pipeline(cats(), {}, monkeypatch)
    hits = cards_with(cs, "asesinan al periodista camilo")
    assert len(hits) == 1
    assert hits[0][1]["section"] == "costarica"
    assert "sucesos" in hits[0][1].get("facets", [])
    for word in ("chinchilla", "colper", "empresarios"):
        assert len(cards_with(cs, word)) == 1, word


@FASE1
def test_parse_date_science_tz():
    # Así llega en science.org (dc:date partido en líneas); antes se descartaban todas sus notas.
    dt = actualizar.parse_date("2026-11-16\nT02:15:00\nZ")
    assert dt is not None and (dt.year, dt.day, dt.hour) == (2026, 16, 2)
    assert actualizar.parse_date("2026-11-13T14:00:00TZ") is not None
    assert actualizar.parse_date("2026-11-13T14:00:00 Z") is not None


@FASE4
def test_canton_sin_mencionar_costa_rica_aceptado():
    import cr_filtro
    it = {"title": "Vecinos de Quepos ganan premio nacional por reciclaje", "summary": "", "kind": "medio", "region": "costarica"}
    sub, why = cr_filtro.judge(it)
    assert why is None and sub


def test_nota_extranjera_de_medio_tico_rechazada():
    import cr_filtro
    it = {"title": "Chile gana premio internacional de turismo sostenible", "summary": "", "kind": "medio", "region": "costarica"}
    assert cr_filtro.judge(it)[1] == "sin ángulo tico"


@FASE4
@FASE4
def test_cantones_en_palabras_clave():
    import regiones
    for t in ("accidente en perez zeledon", "lluvias en sarapiqui", "festival en quepos", "golfito recibe crucero", "upala"):
        assert regiones.KW["costarica"].search(t), t


@FASE1
def test_feed_congelado_se_marca():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 11, 17, 19, tzinfo=timezone.utc)
    assert actualizar.frozen_reason("expansion", now - timedelta(days=12), now).startswith("congelado")
    assert actualizar.frozen_reason("science", None, now).startswith("congelado")
    assert actualizar.frozen_reason("bbc-top", now - timedelta(hours=2), now) is None
    assert actualizar.frozen_reason("econ-int", now - timedelta(days=6), now) is None   # semanal
