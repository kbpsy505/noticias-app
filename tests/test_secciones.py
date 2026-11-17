"""Fase 7: portada «Hoy», índice de 6 secciones y «En desarrollo» por sección."""
import pytest
import actualizar as A


def st(i, sec, facets=(), outlets=3, stale=False):
    return {"id": i, "section": sec, "facets": list(facets), "outlets": outlets, "stale": stale,
            "lastArticle": "2026-11-17T10:00:00Z", "sources": []}


def cats():
    return [
        {"id": "costarica", "stories": [st("costarica-1", "costarica"), st("costarica-2", "costarica", ["sucesos"])]},
        {"id": "mundo", "stories": [st("mundo-1", "mundo", outlets=9), st("mundo-2", "mundo", stale=True)]},
        {"id": "guerras", "stories": [st("guerras-1", "mundo", ["conflictos"])]},
        {"id": "finanzas", "stories": [st("finanzas-1", "dinero", ["finanzas"])]},
        {"id": "buenas", "stories": [st("buenas-1", "avances", ["buenas"], outlets=1),
                                     st("buenas-2", "avances", ["buenas"], outlets=4)]},
        {"id": "deportes", "kind": "scores+news", "stories": [st("deportes-1", "deportes")]},
        {"id": "posibles", "stories": [{"id": "posibles-1", "outlets": 2, "chips": [{"id": "cripto", "label": "Cripto"}],
                                        "sources": []}]},
    ]


def test_posibles_van_a_su_seccion():
    c = cats()
    A.assign_sections([x for x in c if x["id"] == "posibles"])
    p = c[-1]["stories"][0]
    assert p["section"] == "dinero" and p["dev"] is True and p["facets"] == ["cripto"]


def test_hoy_tiene_ritmo_y_cierre_con_buena_noticia():
    c = cats()
    A.assign_sections([x for x in c if x["id"] == "posibles"])
    home = A.build_home(c)
    ids = [b["id"] for b in home["blocks"]]
    assert ids[0] == "ancla" and ids[-1] == "cierre"
    by = {b["id"]: b.get("stories", []) for b in home["blocks"]}
    assert by["cierre"] == ["buenas-2"]                        # la mejor buena noticia cierra
    assert "guerras-1" in by["conflictos"] and "costarica-2" in by["conflictos"] or "costarica-2" in by["cercano"]
    assert "mundo-2" not in sum(by.values(), [])               # lo viejo no entra a Hoy
    flat = [i for b in home["blocks"] if not b.get("dev") for i in b.get("stories", [])]
    assert len(flat) == len(set(flat)) == home["count"]       # cada historia una sola vez
    assert by["desarrollo"] == ["posibles-1"]


def test_indice_de_secciones_y_validacion():
    c = cats()
    A.assign_sections([x for x in c if x["id"] == "posibles"])
    home = A.build_home(c)
    idx = A.sections_index(c, home)
    assert [s["id"] for s in idx] == ["hoy", "costarica", "mundo", "dinero", "deportes", "avances"]
    assert {s["id"]: s["dev"] for s in idx}["dinero"] == 1
    payload = {"updatedAt": "x", "categories": c, "home": home, "sections": idx}
    A.validate_payload(payload)
    home["blocks"][1]["stories"].append("no-existe")
    with pytest.raises(ValueError):
        A.validate_payload(payload)
