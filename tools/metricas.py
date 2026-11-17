#!/usr/bin/env python3
"""Métricas de noticias.json (solo lectura). Compara una o más salidas: antes (main) y después (rama).

Uso: python tools/metricas.py antes.json despues.json [--md salida.md] [--json salida.json]

Mide tarjetas, historias únicas (enlaces compartidos o titular parecido), duplicados entre pestañas,
historias por sección (las 6 nuevas), frescura, Posibles/En desarrollo, enlaces de Google Noticias,
feeds con fallo o congelados y rechazos del filtro tico. Sirve para el formato viejo y el nuevo.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlparse

CONSENSUS_TABS = ("costarica", "finanzas", "cripto", "politica", "ciencias", "mundo", "sucesos", "guerras", "buenas", "deportes")
SECTIONS = ["costarica", "mundo", "dinero", "deportes", "avances"]
CAT_TO_SECTION = {"costarica": "costarica", "politica": "mundo", "sucesos": "mundo", "guerras": "mundo", "mundo": "mundo",
                  "finanzas": "dinero", "cripto": "dinero", "buenas": "avances", "ciencias": "avances", "deportes": "deportes"}
STOP = set("de la el los las y en a del un una por con para que se al es su sus the of to in and on for is at as by with from".split())


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if s else None


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def toks(t):
    return {w for w in re.findall(r"[a-z0-9]+", fold(t)) if w not in STOP and len(w) > 2}


def ukey(u):
    p = urlparse(u)
    return (p.netloc.replace("www.", "") + p.path.rstrip("/")).lower()


def story_section(cat_id, s):
    if s.get("section"):
        return s["section"]
    if cat_id == "costarica" or s.get("cr") or s.get("region") == "costarica":
        return "costarica"
    return CAT_TO_SECTION.get(cat_id)


def last_article(s):
    v = [x.get("publishedAt") for x in s.get("sources", []) if x.get("publishedAt")]
    return max(v) if v else (s.get("lastArticle") or s.get("lastSeen"))


def analyse(path):
    d = json.load(open(path, encoding="utf-8"))
    now = ts(d["updatedAt"])
    cards = []
    for c in d["categories"]:
        for s in c["stories"]:
            cards.append((c["id"], s))
    cons = [(cid, s) for cid, s in cards if cid in CONSENSUS_TABS]
    # Historias únicas: unión por enlace compartido o titular parecido (Jaccard >= 0,6 con 4+ palabras).
    n = len(cons)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_url = defaultdict(list)
    tk = []
    for i, (cid, s) in enumerate(cons):
        for x in s.get("sources", []):
            by_url[ukey(x["url"])].append(i)
        tk.append(toks(s.get("headline", "")) | toks(s.get("headlineEs") or "") | toks(s.get("headlineEn") or ""))
    for lst in by_url.values():
        for j in lst[1:]:
            parent[find(j)] = find(lst[0])
    for i in range(n):
        for j in range(i + 1, n):
            a, b = tk[i], tk[j]
            if len(a) >= 4 and len(b) >= 4 and len(a & b) / len(a | b) >= 0.6:
                parent[find(j)] = find(i)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    multi_tab = [g for g in groups.values() if len({cons[i][0] for i in g}) > 1]
    same_tab = sum(len(g) - len({cons[i][0] for i in g}) for g in groups.values())
    sec_groups = defaultdict(set)
    sec_cards = Counter()
    for root, g in groups.items():
        for i in g:
            sec = story_section(cons[i][0], cons[i][1])
            sec_groups[sec].add(root)
            sec_cards[sec] += 1
    cross_section = sum(1 for g in groups.values() if len({story_section(cons[i][0], cons[i][1]) for i in g}) > 1)
    with_also = sum(1 for _, s in cons if s.get("alsoIn"))
    # Frescura (horas desde la nota más reciente de cada historia hasta updatedAt).
    ages = defaultdict(list)
    for cid, s in cons:
        la = last_article(s)
        if la:
            ages[story_section(cid, s)].append((now - ts(la)) / 3600)
    all_ages = [a for v in ages.values() for a in v]
    fresh = Counter(s.get("fresh") for _, s in cons)
    stale = sum(1 for _, s in cons if s.get("stale"))
    gn = sum(1 for _, s in cards for x in s.get("sources", []) if "news.google.com" in x.get("url", ""))
    pos = next((c for c in d["categories"] if c["id"] == "posibles"), {"stories": []})
    prep = d.get("possible") or {}
    # Feeds
    live_fail = [f for f in d.get("feedsFailed", [])]
    known = {k for k in ("reuters", "ap", "washingtonpost", "cnn-espanol", "efe", "independent", "timesofisrael-directo",
                         "semafor", "meduza", "dw-es-mundo", "arabnews / the national", "ukrinform", "wsj-world")}
    main_live_fail = [f["id"] for f in live_fail if f["id"] not in known and not f.get("known") and "conocido" not in (f.get("error") or "")
                      and not (f.get("error") or "").startswith("congelado")]
    frozen = [f["id"] for f in d.get("feedsOk", []) if f.get("itemsInFeed", 0) > 0 and f.get("kept", 0) == 0]
    frozen_marked = [f["id"] for f in live_fail if (f.get("error") or "").startswith("congelado")]
    mod_fail = Counter()
    for name, rep in (("buenas", d.get("goodNews") or {}), ("regiones", d.get("regions") or {}),
                      ("cripto", d.get("crypto") or {}), ("deportesNoticias", d.get("sportsNews") or {})):
        mod_fail[name] = len(rep.get("feedsFailed", []) or [])
    for tname, rep in (d.get("topics") or {}).items():
        mod_fail[tname] = len((rep or {}).get("feedsFailed", []) or [])
    cr_rej = ((d.get("goodNews") or {}).get("cr") or {}).get("rejected") or {}
    sports_news = 0
    dep = next((c for c in d["categories"] if c["id"] == "deportes"), None)
    if dep:
        sports_news = len(dep["stories"])
    home = d.get("home") or {}
    return {
        "file": path, "updatedAt": d["updatedAt"],
        "cards": len(cons), "unique": len(groups), "dupCards": len(cons) - len(groups),
        "storiesInSeveralTabs": len(multi_tab), "dupSameTab": same_tab, "storiesInSeveralSections": cross_section,
        "withAlsoIn": with_also,
        "perTab": {c["id"]: len(c["stories"]) for c in d["categories"]},
        "perSectionUnique": {s: len(sec_groups.get(s, ())) for s in SECTIONS},
        "perSectionCards": {s: sec_cards.get(s, 0) for s in SECTIONS},
        "ageNewestH": round(min(all_ages), 1) if all_ages else None,
        "ageMedianH": round(statistics.median(all_ages), 1) if all_ages else None,
        "ageOldestH": round(max(all_ages), 1) if all_ages else None,
        "ageMedianBySection": {s: round(statistics.median(ages[s]), 1) if ages.get(s) else None for s in SECTIONS},
        "fresh": dict(fresh), "stalePct": round(100 * stale / max(1, len(cons)), 1),
        "googleNewsLinks": gn,
        "posiblesShown": len(pos["stories"]), "posiblesAfterDedupe": prep.get("afterDedupe"),
        "posiblesHidden": (prep.get("afterDedupe") or 0) - len(pos["stories"]),
        "feedsOk": len(d.get("feedsOk", [])), "mainFeedsFailedLive": main_live_fail,
        "mainFeedsFrozenUnmarked": frozen, "mainFeedsFrozenMarked": frozen_marked,
        "moduleFeedsFailed": dict(mod_fail), "moduleFeedsFailedTotal": sum(mod_fail.values()),
        "crRejected": cr_rej, "sportsNews": sports_news,
        "homeItems": len(home.get("items", [])) if isinstance(home, dict) else None,
        "itemsGathered": (d.get("stats") or {}).get("itemsGathered"),
        "groupsWith3or4Outlets": (d.get("regions") or {}).get("groupsWith3or4Outlets"),
    }


ROWS = [("Tarjetas (pestañas de consenso + Buenas + Deportes)", "cards"), ("Historias únicas", "unique"),
        ("Tarjetas repetidas (tarjetas − únicas)", "dupCards"), ("Historias en 2+ pestañas", "storiesInSeveralTabs"),
        ("Historias en 2+ secciones nuevas", "storiesInSeveralSections"), ("Repetidas dentro de la misma pestaña", "dupSameTab"),
        ("Tarjetas con chip «También en»", "withAlsoIn"),
        ("Nota más reciente (h)", "ageNewestH"), ("Mediana de edad (h)", "ageMedianH"), ("Historia más vieja (h)", "ageOldestH"),
        ("% «Anteriores» (stale)", "stalePct"), ("Enlaces news.google.com", "googleNewsLinks"),
        ("Posibles / En desarrollo mostrados", "posiblesShown"), ("Posibles ocultos por el tope", "posiblesHidden"),
        ("Feeds principales OK", "feedsOk"), ("Feeds de módulos con fallo en vivo", "moduleFeedsFailedTotal"),
        ("Noticias deportivas", "sportsNews"), ("Notas recogidas (pool)", "itemsGathered")]


def fmt(v):
    if isinstance(v, list):
        return f"{len(v)}" + (f" ({', '.join(v[:6])}{'…' if len(v) > 6 else ''})" if v else "")
    return "—" if v is None else str(v)


def table(res):
    hdr = "| Métrica | " + " | ".join(r["label"] for r in res) + " |\n|---|" + "---|" * len(res) + "\n"
    out = hdr
    for label, k in ROWS:
        out += f"| {label} | " + " | ".join(fmt(r[k]) for r in res) + " |\n"
    out += "| Feeds principales con fallo en vivo | " + " | ".join(fmt(r["mainFeedsFailedLive"]) for r in res) + " |\n"
    out += "| Feeds principales que responden pero aportan 0 notas | " + " | ".join(fmt(r["mainFeedsFrozenUnmarked"]) for r in res) + " |\n"
    out += "| Feeds principales marcados «congelado» | " + " | ".join(fmt(r["mainFeedsFrozenMarked"]) for r in res) + " |\n"
    for s in SECTIONS:
        out += f"| Sección {s}: historias únicas (tarjetas) | " + " | ".join(
            f"{r['perSectionUnique'][s]} ({r['perSectionCards'][s]})" for r in res) + " |\n"
    for s in SECTIONS:
        out += f"| Sección {s}: mediana de edad (h) | " + " | ".join(fmt(r["ageMedianBySection"][s]) for r in res) + " |\n"
    tabs = sorted({t for r in res for t in r["perTab"]})
    for t in tabs:
        out += f"| Pestaña `{t}` (tarjetas) | " + " | ".join(fmt(r["perTab"].get(t)) for r in res) + " |\n"
    reasons = sorted({k for r in res for k in r["crRejected"]})
    for k in reasons:
        out += f"| Filtro tico: «{k}» | " + " | ".join(fmt(r["crRejected"].get(k)) for r in res) + " |\n"
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="ruta[=etiqueta]")
    ap.add_argument("--md")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = []
    for f in a.files:
        path, _, label = f.partition("=")
        r = analyse(path)
        r["label"] = label or path
        res.append(r)
    md = table(res)
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
