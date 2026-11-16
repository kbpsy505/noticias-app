"""Agrupación, umbral de 3 medios, aliases de organización y Posibles."""
from actualizar import (
    MIN_OUTLETS, build_vectors, cluster, make_story,
)
from helpers import pool_item

# Titulares distintos, mismo hecho, con términos distintivos compartidos
# (Maduro, Nueva York, captura, juicio).
T_ES_1 = "Maduro enfrenta un juicio en Nueva York tras su captura"
T_ES_2 = "Tras la captura de Maduro, arranca el juicio en Nueva York"
T_EN = "Maduro faces trial in New York after his capture"
SUM = "El exmandatario Maduro enfrenta un juicio en Nueva York tras su captura, según el tribunal."


FILLER_TOPICS = ["volcan", "cosecha", "museo", "puerto", "festival", "biblioteca", "tranvia", "glaciar",
                 "hospital", "aeropuerto", "estadio", "represa", "mercado", "teatro", "parque", "universidad"]


def _filler(n=80):
    """Corpus de relleno: cluster() descarta términos con df > 6% del corpus, así que con 3 notas
    sueltas nada sería 'distintivo'. En producción hay ~2 000 notas por corrida."""
    out = []
    for i in range(n):
        a = FILLER_TOPICS[i % len(FILLER_TOPICS)]
        b = FILLER_TOPICS[(i * 7 + 3) % len(FILLER_TOPICS)]
        out.append(pool_item(f"Nota de relleno {i} sobre {a} y {b} en ciudad{i}", f"fill{i}",
                             summary=f"Texto de relleno {i} {a} {b} zona{i} distrito{i}."))
    return out


def _cluster(items):
    items.extend(_filler())
    idf, df = build_vectors(items)
    groups, sims = cluster(items, idf, df)
    return groups, sims, idf


def _org_counts(items, groups):
    out = []
    for g in groups:
        orgs = {items[i]["org"] for i in g}
        out.append((len(g), len(orgs), orgs))
    return out


def test_three_distinct_orgs_form_consensus():
    items = [
        pool_item(T_ES_1, "bbc", source="BBC", lang="es"),
        pool_item(T_ES_2, "elpais", source="El País", lang="es", hours_ago=1.2),
        pool_item(T_EN, "nyt", source="The New York Times", lang="en", hours_ago=0.8, summary=SUM),
    ]
    groups, sims, _ = _cluster(items)
    big = [g for g in groups if len({items[i]["org"] for i in g}) >= MIN_OUTLETS]
    assert len(big) == 1, _org_counts(items, groups)
    story = make_story(big[0], items, sims)
    assert story["outlets"] == 3
    assert set(story["languages"]) == {"es", "en"}
    assert story["headlineEs"]
    assert story["headlineEn"]


def test_same_org_three_times_does_not_count_as_three_outlets():
    """BBC y BBC Mundo comparten org 'bbc' en feeds.py; tres notas del mismo org no son consenso."""
    items = [
        pool_item(T_ES_1, "bbc", source="BBC", lang="en", path="world"),
        pool_item(T_ES_2, "bbc", source="BBC Mundo", lang="es", path="mundo"),
        pool_item(T_EN, "bbc", source="BBC Mundo", lang="es", path="latam"),
    ]
    groups, sims, _ = _cluster(items)
    # Pueden agruparse, pero outlets==1
    for g in groups:
        if len(g) >= 2:
            story = make_story(g, items, sims)
            assert story["outlets"] == 1
            assert story["outlets"] < MIN_OUTLETS


def test_two_orgs_are_below_consensus_threshold():
    items = [
        pool_item(T_ES_1, "bbc", source="BBC"),
        pool_item(T_ES_2, "elpais", source="El País", hours_ago=1.1),
    ]
    groups, sims, _ = _cluster(items)
    matched = [g for g in groups if len(g) == 2]
    assert matched, "se esperaba agrupar las dos notas"
    story = make_story(matched[0], items, sims)
    assert story["outlets"] == 2
    assert story["outlets"] < MIN_OUTLETS  # irían a Posibles, no a consenso


def test_unrelated_stories_are_not_merged():
    items = [
        pool_item(T_ES_1, "bbc", source="BBC"),
        pool_item(T_ES_2, "elpais", source="El País"),
        pool_item(
            "La Caja anuncia un recorte al presupuesto de vivienda en Costa Rica",
            "nacion", source="La Nación",
            summary="La Caja y el gobierno anuncian recortes al presupuesto de vivienda.",
        ),
        pool_item(
            "Recorte al presupuesto de vivienda de la Caja genera debate en Costa Rica",
            "crhoy", source="CRHoy", hours_ago=1.3,
            summary="Hay debate por el recorte al presupuesto de vivienda de la Caja.",
        ),
    ]
    groups, _, _ = _cluster(items)
    # Ningún grupo debería mezclar Maduro con la Caja
    for g in groups:
        titles = " ".join(items[i]["title"] for i in g)
        if "Maduro" in titles:
            assert "Caja" not in titles
        if "Caja" in titles:
            assert "Maduro" not in titles


def test_earthquakes_in_different_countries_do_not_merge():
    items = [
        pool_item("Temblor de magnitud 6.2 se siente en Guatemala esta madrugada", "prensa", source="Prensa Libre"),
        pool_item("Temblor de magnitud 6.2 se siente en Costa Rica esta madrugada", "nacion", source="La Nación"),
    ]
    groups, _, _ = _cluster(items)
    merged = [g for g in groups if len(g) == 2]
    assert not merged, "sismos en países distintos no deben unirse"


def test_min_outlets_constant_is_three():
    assert MIN_OUTLETS == 3
