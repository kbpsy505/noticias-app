#!/usr/bin/env python3
"""Descarga titulares reales de RSS públicos y escribe noticias.json.

No inventa titulares. Si un feed falla o no trae actualidad, se omite.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "noticias.json"
REFRESH_HOURS = 3
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
MAX_PER = 12
NEWS_DAYS = 12
SCIENCE_DAYS = 45

# id, url, source, lang, default category (None = clasificar)
FEEDS = [
    ("bbc-world", "https://feeds.bbci.co.uk/news/world/rss.xml", "BBC", "en", "mundo"),
    ("bbc-politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "BBC", "en", "politica"),
    ("bbc-business", "https://feeds.bbci.co.uk/news/business/rss.xml", "BBC", "en", "finanzas"),
    ("bbc-science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "BBC", "en", "ciencias"),
    ("bbc-me", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "BBC", "en", "mundo"),
    ("bbc-europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "BBC", "en", "mundo"),
    ("bbc-africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "BBC", "en", "mundo"),
    ("bbc-asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml", "BBC", "en", "mundo"),
    ("bbc-uk", "https://feeds.bbci.co.uk/news/uk/rss.xml", "BBC", "en", None),
    ("bbc-top", "https://feeds.bbci.co.uk/news/rss.xml", "BBC", "en", None),
    ("bbc-mundo", "https://feeds.bbci.co.uk/mundo/rss.xml", "BBC Mundo", "es", None),
    ("elpais-int", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada", "El País", "es", "mundo"),
    ("elpais-esp", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/portada", "El País", "es", "politica"),
    ("elpais-eco", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada", "El País", "es", "finanzas"),
    ("elpais-soc", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/sociedad/portada", "El País", "es", "sucesos"),
    ("elpais-ciencia", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/ciencia/portada", "El País", "es", "ciencias"),
    ("elpais-en", "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada", "El País", "en", None),
    ("elmundo-portada", "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml", "El Mundo", "es", None),
    ("elmundo-int", "https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml", "El Mundo", "es", "mundo"),
    ("elmundo-esp", "https://e00-elmundo.uecdn.es/elmundo/rss/espana.xml", "El Mundo", "es", "politica"),
    ("elmundo-eco", "https://e00-elmundo.uecdn.es/elmundo/rss/economia.xml", "El Mundo", "es", "finanzas"),
    ("elmundo-ciencia", "https://e00-elmundo.uecdn.es/elmundo/rss/ciencia.xml", "El Mundo", "es", "ciencias"),
    ("econ-int", "https://www.economist.com/international/rss.xml", "The Economist", "en", "mundo"),
    ("econ-fin", "https://www.economist.com/finance-and-economics/rss.xml", "The Economist", "en", "finanzas"),
    ("econ-biz", "https://www.economist.com/business/rss.xml", "The Economist", "en", "finanzas"),
    ("econ-us", "https://www.economist.com/united-states/rss.xml", "The Economist", "en", "politica"),
    ("ft-home", "https://www.ft.com/rss/home", "Financial Times", "en", "finanzas"),
    ("ft-world", "https://www.ft.com/world?format=rss", "Financial Times", "en", "mundo"),
    ("ft-markets", "https://www.ft.com/markets?format=rss", "Financial Times", "en", "finanzas"),
    ("bbg-markets", "https://feeds.bloomberg.com/markets/news.rss", "Bloomberg", "en", "finanzas"),
    ("bbg-politics", "https://feeds.bloomberg.com/politics/news.rss", "Bloomberg", "en", "politica"),
    ("bbg-econ", "https://feeds.bloomberg.com/economics/news.rss", "Bloomberg", "en", "finanzas"),
    ("nature", "https://www.nature.com/nature.rss", "Nature", "en", "ciencias"),
    ("science", "https://www.science.org/rss/news_current.xml", "Science", "en", "ciencias"),
]

# Intentos que no aportan titulares de actualidad. Se registran, no se publican.
EXTRA_FAILS = [
    ("reuters", "https://www.reuters.com/arc/outboundfeeds/v3/all/?outputType=xml", "HTTP 404; Reuters no ofrece RSS público de titulares"),
    ("reuters-world", "https://www.reuters.com/world/rss", "HTTP 401"),
    ("ap", "https://apnews.com/index.rss", "HTTP 403; AP no publica un RSS abierto utilizable"),
    ("elmundo-sucesos", "https://e00-elmundo.uecdn.es/elmundo/rss/sucesos.xml", "HTTP 404"),
    ("wsj-world", "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "Responde, pero los ítems están congelados en enero de 2025; no es un feed vivo"),
    ("afp", "https://www.afp.com/en/rss.xml", "No es un cable de noticias: solo notas institucionales antiguas (2012-2021)"),
]

ALLOWED_HOSTS = {
    "bbc.co.uk", "www.bbc.co.uk", "bbc.com", "www.bbc.com",
    "elpais.com", "www.elpais.com", "english.elpais.com",
    "elmundo.es", "www.elmundo.es",
    "economist.com", "www.economist.com",
    "ft.com", "www.ft.com",
    "bloomberg.com", "www.bloomberg.com",
    "nature.com", "www.nature.com",
    "science.org", "www.science.org",
}

WAR = re.compile(
    r"("
    r"\b(ucrania|ukraine|kyiv|kiev|odesa|odessa|gaza|ham[aá]s|hamas|hezbol[aá]|hezbollah|"
    r"hut[ií]es|houthis|houthi)\b|"
    r"guerra en|iran war|the iran war|guerra de|bombardea|bombardeo|airstrike|"
    r"drone attack|ataques? (rusos|israel[ií]es|con drones)|missile strike|"
    r"alto el fuego|ceasefire|front-line|front line|"
    r"strikes on kyiv|russian drone|russian missile|"
    r"\b(rusia|russia|putin)\b.{0,48}\b(guerra|war|ucrania|ukraine|kyiv|kiev|bombar|drone|misil|missile|invasi)|"
    r"\b(guerra|war|bombar|drone strike|misil|missile)\b.{0,48}\b(rusia|russia|putin|ucrania|ukraine|iran|ir[aá]n)|"
    r"\b(sud[aá]n|sudan)\b.{0,40}\b(war|guerra|battle|batalla)|"
    r"yemen.{0,30}(war|guerra|houthi|hut[ií])"
    r")",
    re.I,
)
SUCESOS = re.compile(
    r"(asesin|murder|homicid|apuñal|stab|hacha|\baxe\b|accidente a[eé]reo|plane crash|"
    r"terremoto|earthquake|incendio|robo |detenid|arrested|"
    r"violencia sexual|sexual harassment|acoso sexual|inundaci|\bflood|"
    r"desaparecid|\bdesaparece\b|\bdesaparecen\b|violaci[oó]n|\brape\b|v[ií]ctima mortal|killed in|muertos por|\bmuere\b|\bmueren\b|"
    r"tiroteo|execution|executed|copiloto|co-pilot|"
    r"alerta roja|granizo|temporal de|lluvias intensas)",
    re.I,
)
STRONG_SCIENCE = re.compile(
    r"(nasa|cient[ií]fic|\bscience\b|dinosaur|f[ií]sica|physics|vacuna|vaccine|starship|"
    r"\bluna\b|\bmoon\b|gen[eé]tic|astronom|biolog|nobel|sat[eé]lite|observator|"
    r"cambio clim|clim[aá]tic|climate change|climate threat|estr[eé]s t[eé]rmico|"
    r"species|especie|oceano|ocean|geol[oó]g|genoma|c[eé]lula|quantum|cu[aá]ntic)",
    re.I,
)
SKIP_PATH = (
    "/deportes/", "/sport/", "/ciclismo/", "/formula1/", "/cultura/", "/cine/",
    "/television/", "/gente/", "/estilo/", "/opinion/", "/opinión/",
    "/videos/", "/video/", "/podcast",
)
POLITICA = re.compile(
    r"(eleccion|election|partido pol|gobierno|government|parlamento|parliament|"
    r"congreso|congress|\bministro|\bminister\b|presidente|president\b|"
    r"\bvoto\b|\bvote\b|campaña electoral|campaign|psoe|\bsánchez\b|"
    r"\btrump\b|\blula\b|bolsonaro|macron|conservative|green party|"
    r"white house|casa blanca|sanchez|parliament)",
    re.I,
)
FINANZAS = re.compile(
    r"(petr[oó]leo|\boil\b|mercado|market|bolsa|\bbanco\b|\bbank\b|inflaci|"
    r"\bfed\b|\bbce\b|\becb\b|acciones|investor|inversor|econom[ií]a|\beconomy\b|"
    r"arancel|tariff|\bempleo\b|bonos|\bbond\b|\blng\b|deuda|\bdebt\b|"
    r"wall street|tipo de inter[eé]s|interest rate|acciones)",
    re.I,
)
CIENCIA = STRONG_SCIENCE
SKIP_TITLE = re.compile(
    r"(newsletter|podcast|bloomberg this weekend|^watch:|^mira:)",
    re.I,
)
SECTION_TITLE = re.compile(
    r"^(guerra en ucrania|guerra ucrania\s*-?\s*rusia|internacional|portada|econom[ií]a)$",
    re.I,
)


def local(tag: str) -> str:
    return tag.split("}")[-1] if tag else ""


def parse_date(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def clean_url(url: str) -> str:
    p = urlparse(url.strip())
    drop = {"at_medium", "at_campaign", "mod"}
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in drop and not k.startswith("syn-")]
    return urlunparse(p._replace(query=urlencode(q), fragment=""))


def host_ok(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in ALLOWED_HOSTS


def classify(title: str, default: str | None, path: str) -> str | None:
    if WAR.search(title):
        return "guerras"
    if SUCESOS.search(title) and default != "ciencias":
        return "sucesos"
    strong = bool(STRONG_SCIENCE.search(title)) or any(
        bit in path for bit in ("/ciencia", "/science", "/nature/")
    )
    off_science = any(bit in path for bit in ("/internacional/", "/sociedad/", "/espana/", "/economia/", "/deportes/", "/cultura/"))
    if default == "ciencias" and (strong or not off_science):
        return "ciencias"
    if default == "finanzas":
        return "finanzas"
    if default == "politica":
        return "politica"
    if default == "sucesos":
        return "sucesos"
    if strong:
        return "ciencias"
    if FINANZAS.search(title):
        return "finanzas"
    if POLITICA.search(title):
        return "politica"
    if any(bit in path for bit in ("/internacional/", "/world/", "/africa/", "/asia/", "/europe/", "/middle-east/", "/middle_east/")):
        return "mundo"
    if default == "ciencias":
        return None
    if default:
        return default
    return None


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=18, context=ctx) as resp:
        return resp.read(400_000)


def parse_items(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    found = []
    for it in root.iter():
        if local(it.tag) not in ("item", "entry"):
            continue
        title = link = date_s = ""
        for ch in list(it):
            ln = local(ch.tag)
            if ln == "title" and not title:
                title = unescape(" ".join("".join(ch.itertext()).split()))
                title = re.sub(r"<[^>]+>", "", title)
                title = " ".join(title.split())
            elif ln == "link" and not link:
                link = (ch.get("href") or "").strip() or unescape((ch.text or "").strip())
            elif ln in ("pubDate", "date", "published", "updated") and not date_s:
                date_s = "".join(ch.itertext()).strip()
        if title and link:
            found.append((title, link, date_s))
    return found


def main():
    now = datetime.now(timezone.utc)
    failures = []
    successes = []
    pool = []
    seen = set()

    for feed_id, url, source, lang, default in FEEDS:
        try:
            raw = fetch(url)
            rows = parse_items(raw)
        except Exception as exc:
            failures.append({"id": feed_id, "source": source, "url": url, "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAIL {feed_id}: {exc}")
            continue
        if not rows:
            failures.append({"id": feed_id, "source": source, "url": url, "error": "sin ítems"})
            print(f"FAIL {feed_id}: empty")
            continue
        kept = 0
        newest = None
        for title, link, date_s in rows:
            if SKIP_TITLE.search(title) or SECTION_TITLE.search(title):
                continue
            if len(title) < 18:
                continue
            url_c = clean_url(link)
            if not url_c.startswith("http") or not host_ok(url_c):
                continue
            path = urlparse(url_c).path.lower()
            if any(bit in path for bit in SKIP_PATH):
                continue
            published = parse_date(date_s)
            if published is None:
                continue
            window = SCIENCE_DAYS if default == "ciencias" else NEWS_DAYS
            if published < now - timedelta(days=window):
                continue
            if published > now + timedelta(hours=6):
                continue
            cat = classify(title, default, path)
            if not cat:
                continue
            key = (urlparse(url_c).netloc + urlparse(url_c).path.rstrip("/")).lower()
            title_key = re.sub(r"\W+", "", title.lower())[:80]
            if key in seen or title_key in seen:
                continue
            seen.add(key)
            seen.add(title_key)
            pool.append({
                "category": cat,
                "lang": lang,
                "title": title,
                "source": source,
                "url": url_c,
                "publishedAt": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "_ts": published.timestamp(),
                "feed": feed_id,
            })
            kept += 1
            newest = published if newest is None or published > newest else newest
        successes.append({
            "id": feed_id,
            "source": source,
            "lang": lang,
            "url": url,
            "itemsInFeed": len(rows),
            "keptBeforeCap": kept,
            "newest": newest.strftime("%Y-%m-%dT%H:%M:%SZ") if newest else None,
        })
        print(f"OK {feed_id} raw={len(rows)} kept={kept}")

    for feed_id, url, reason in EXTRA_FAILS:
        failures.append({"id": feed_id, "source": feed_id, "url": url, "error": reason})

    categories = ["sucesos", "politica", "finanzas", "mundo", "ciencias", "guerras"]
    chosen = []
    counts = {c: {"es": 0, "en": 0} for c in categories}
    for cat in categories:
        for lang in ("es", "en"):
            group = [x for x in pool if x["category"] == cat and x["lang"] == lang]
            group.sort(key=lambda x: x["_ts"], reverse=True)
            if cat == "ciencias":
                preferred = [x for x in group if x["source"] in ("Nature", "Science")]
                others = [x for x in group if x["source"] not in ("Nature", "Science")]
                take = (preferred[:6] + others)[:MAX_PER]
                take.sort(key=lambda x: x["_ts"], reverse=True)
            else:
                take = group[:MAX_PER]
            counts[cat][lang] = len(take)
            for item in take:
                item = dict(item)
                item.pop("_ts", None)
                item.pop("feed", None)
                chosen.append(item)

    updated = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    nxt = (now + timedelta(hours=REFRESH_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "updatedAt": updated,
        "nextRefreshAt": nxt,
        "refreshHours": REFRESH_HOURS,
        "timezoneNote": "Las horas de la interfaz se muestran en America/Costa_Rica.",
        "categories": [
            {"id": "sucesos", "label": "Sucesos"},
            {"id": "politica", "label": "Política"},
            {"id": "finanzas", "label": "Mundo de finanzas"},
            {"id": "mundo", "label": "Mundo"},
            {"id": "ciencias", "label": "Ciencias"},
            {"id": "guerras", "label": "Guerras actuales"},
        ],
        "counts": counts,
        "sourcesUsed": sorted({s["source"] for s in successes if s["keptBeforeCap"] > 0}),
        "feedsOk": successes,
        "feedsFailed": failures,
        "items": chosen,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nCOUNTS")
    for cat in categories:
        print(f"  {cat}: ES={counts[cat]['es']} EN={counts[cat]['en']}")
    print("items", len(chosen))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
