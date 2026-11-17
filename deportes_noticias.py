"""Noticias deportivas de consenso para la pestaña Deportes (Arreglo 7 del plan de mejoras de contenido).

Mismo patrón que cripto.py: feeds deportivos dedicados (verificados con RSS vivo el 2026-11-17), agrupado con
el mismo agrupador (cluster + merge_pass), 3+ medios distintos para salir como historia y 2 medios para
«En desarrollo». Los marcadores de ESPN (resultados.py) siguen arriba y sin cambios; esto va debajo.
Fuera: apuestas y cuotas, «dónde ver», en vivo/minuto a minuto, previas vacías, galerías, videos y pódcast.
"""
from __future__ import annotations

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import quote, urlparse

import actualizar as A

MIN_OUTLETS = 3
MAX_STORIES = 30
SPORT_HOURS = 48
GNEWS = {"en": "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en",
         "es": "https://news.google.com/rss/search?q={}&hl=es-419&gl=CR&ceid=CR:es-419"}
GN_SUFFIX = re.compile(r"\s+[-|–]\s+[^-|–]{2,45}$")

# (id, url o «gn:consulta», medio, organización, idioma)
SPORT_FEEDS = [
    ("dep-bbc", "https://feeds.bbci.co.uk/sport/rss.xml", "BBC Sport", "bbc", "en"),
    ("dep-guardian", "https://www.theguardian.com/sport/rss", "The Guardian", "guardian", "en"),
    ("dep-guardian-futbol", "https://www.theguardian.com/football/rss", "The Guardian", "guardian", "en"),
    ("dep-sky", "https://www.skysports.com/rss/12040", "Sky Sports", "sky", "en"),
    ("dep-athletic", "https://www.nytimes.com/athletic/rss/news/", "The Athletic", "nyt", "en"),
    ("dep-cbs", "https://www.cbssports.com/rss/headlines/", "CBS Sports", "cbs", "en"),
    ("dep-fox", "https://www.foxsports.com/feedout/syndicatedContent?categoryId=0", "FOX Sports", "fox", "en"),
    ("dep-espn", "gn:site:espn.com", "ESPN", "espn", "en"),
    ("dep-espn-es", "gn:site:espndeportes.espn.com OR site:espn.com.mx", "ESPN Deportes", "espn", "es"),
    ("dep-as", "https://feeds.as.com/mrss-s/pages/as/site/as.com/portada", "AS", "as", "es"),
    ("dep-elpais", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada", "El País", "elpais", "es"),
    ("dep-elmundo", "https://e00-elmundo.uecdn.es/elmundodeporte/rss/portada.xml", "El Mundo", "unidad-editorial", "es"),
    ("dep-mundodeportivo", "https://www.mundodeportivo.com/rss/home", "Mundo Deportivo", "mundodeportivo", "es"),
    ("dep-sport", "https://www.sport.es/es/rss/last-news/news.xml", "Sport", "sport-es", "es"),
    ("dep-infobae", "https://www.infobae.com/arc/outboundfeeds/rss/category/deportes/", "Infobae", "infobae", "es"),
    ("dep-ole", "https://www.ole.com.ar/rss/ultimas-noticias/", "Olé", "ole", "es"),
    ("dep-f24", "https://www.france24.com/es/deportes/rss", "France 24 Español", "france24", "es"),
    ("dep-nacion-cr", "https://www.nacion.com/arc/outboundfeeds/rss/category/puro-deporte/?outputType=xml", "La Nación (Costa Rica)", "grupo-nacion", "es"),
    ("dep-lateja", "https://www.lateja.cr/arc/outboundfeeds/rss/category/deportes/?outputType=xml", "La Teja", "grupo-nacion", "es"),
    ("dep-teletica", "gn:site:teletica.com/deportes", "Teletica", "teletica", "es"),
    ("dep-crhoy", "gn:site:crhoy.com/deportes", "CRHoy", "crhoy", "es"),
]
SPORT_KNOWN_FAILS = [
    ("espn-rss", "https://www.espn.com/espn/rss/news", "ESPN responde 202 sin ítems; se usa Google Noticias site:espn.com"),
    ("marca", "https://e00-marca.uecdn.es/rss/portada.xml", "Marca: RSS congelado (última nota del 10 nov 2026)"),
    ("diarioextra-deportes", "https://www.diarioextra.com/rss/deportes", "403"),
]

SKIP = re.compile(
    r"(?i)(apuesta|betting|\bodds\b|\bpicks?\b|parlay|pron[oó]stico|predicci[oó]n|prediction|best bets?|"
    r"d[oó]nde ver|canal(es)? para ver|hora y canal|qu[eé] canal|horario y canal|por tv|transmisi[oó]n en|c[oó]mo ver|where to watch|how to watch|\bstream\w*\b|tv channel|canal de tv|a qu[eé] hora|"
    r"en vivo|en directo|\blive\b|minuto a minuto|as it happened|player ratings|calificaciones|"
    r"\bquiz\b|crucigrama|horóscopo|podcast|p[oó]dcast|\bvideo\b|\bv[ií]deo\b|galer[ií]a|\bfotos\b|in pictures|"
    r"fantasy|ofertas?|descuento|black friday|merch|camiseta a la venta|sponsored|patrocinad)")


# SKIP_PATH de actualizar.py descarta /sport/ y /deportes/ (bien para las demás pestañas); aquí solo formatos.
SKIP_PATH = re.compile(r"/(opinion|opini%c3%b3n|opinión|commentisfree|columnas?|blogs?|videos?|av|audio|live|en-vivo|directo|podcasts?|galerias?|gallery|fotos|picture|quiz|apuestas|betting)(/|-|$)")


def fetch(feed):
    fid, url, source, org, lang = feed
    if not url.startswith("gn:"):
        return A.fetch_feed(feed)
    real = GNEWS[lang].format(quote("when:2d " + url[3:]))
    _, rows, err = A.fetch_feed((fid, real) + feed[2:])
    return feed, [(GN_SUFFIX.sub("", t), l, d, "") for t, l, d, _ in rows or []] or None, err


def build(now, general_pool=()):
    """Devuelve (historias, candidatas de 2 medios, informe). general_pool: notas generales del día, solo como
    corpus de fondo para medir qué términos son raros (como cripto.py)."""
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(fetch, SPORT_FEEDS))
    pool, seen = [], set()
    feeds_ok, feeds_failed, rejected = [], [], Counter()
    for feed, rows, err in results:
        fid, url, source, org, lang = feed
        if err or not rows:
            feeds_failed.append({"id": fid, "source": source, "url": url, "error": err or "sin ítems"})
            continue
        kept = 0
        for title, link, date_s, desc in rows:
            if len(title) < 18 or A.SKIP_TITLE.search(title) or SKIP.search(title):
                rejected["formato/apuestas/en vivo"] += 1
                continue
            u = A.clean_url(link)
            if not A.is_safe_http_url(u) or SKIP_PATH.search(urlparse(u).path.lower()):
                rejected["sección no noticiosa"] += 1
                continue
            pub = A.parse_date(date_s)
            if pub is None or pub > now + timedelta(hours=3) or pub < now - timedelta(hours=SPORT_HOURS):
                continue
            key = (urlparse(u).netloc.replace("www.", "") + urlparse(u).path.rstrip("/")).lower()
            tkey = org + "|" + re.sub(r"\W+", "", A.fold(title.lower()))[:90]
            if key in seen or tkey in seen:
                continue
            seen.update((key, tkey))
            summary = desc if desc and A.fold(desc.lower())[:60] != A.fold(title.lower())[:60] else ""
            pool.append({"title": title, "url": u, "source": source, "org": org, "lang": lang,
                         "summary": A.trim(summary), "category": "deportes", "feed": fid,
                         "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "_ts": pub.timestamp()})
            kept += 1
        feeds_ok.append({"id": fid, "source": source, "url": url, "itemsInFeed": len(rows), "kept": kept})
    stories, candidates = [], []
    by_count = Counter()
    if pool:
        urls = {it["url"] for it in pool}
        background = [{k: it[k] for k in ("title", "summary", "lang", "_ts")}
                      for it in general_pool if it.get("url") not in urls]
        idf, df = A.build_vectors(pool + background)
        groups, sims = A.cluster(pool, idf, df, n_ref=len(pool) + len(background))
        groups, _ = A.merge_pass(groups, pool, idf)
        for g in groups:
            k = len({pool[i]["org"] for i in g})
            by_count[k] += 1
            if k < 2:
                continue
            st = A.make_story(g, pool, sims)
            (stories if k >= MIN_OUTLETS else candidates).append(st)
    stories.sort(key=lambda s: (s["outlets"], s["_last"]), reverse=True)
    stories = stories[:MAX_STORIES]
    for c in candidates:
        c["category"] = "deportes"
    report = {"itemsGathered": len(pool), "feedsOk": feeds_ok, "feedsFailed": feeds_failed,
              "knownFails": [{"id": a, "url": b, "error": c} for a, b, c in SPORT_KNOWN_FAILS],
              "rejected": dict(rejected), "groupsByOutletCount": {str(k): v for k, v in sorted(by_count.items())},
              "stories": len(stories), "candidates": len(candidates)}
    return stories, candidates, report
