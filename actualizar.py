#!/usr/bin/env python3
"""Briefing de consenso, solo con código (sin IA ni claves).

1. Descarga RSS públicos (feeds.py).
2. Normaliza títulos y resúmenes en español e inglés a un vocabulario común.
3. Agrupa notas sobre el mismo hecho (TF-IDF + coincidencia de términos
   distintivos + ventana de tiempo), aunque estén en idiomas distintos.
4. Conserva solo los grupos que publican 5 o más medios distintos (MIN_OUTLETS).
5. Escribe noticias.json para la página.

No inventa nada: cada texto mostrado sale tal cual de un feed.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import ssl
import sys
import time
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from xml.etree import ElementTree as ET

from feeds import FEEDS, KNOWN_FAILS
from vocab import PHRASES, STOP, WORDS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "noticias.json"
DEBUG = "--debug" in sys.argv
REFRESH_HOURS = 3
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

NEWS_HOURS = 48          # antigüedad máxima de una nota (noticias)
SCIENCE_HOURS = 24 * 7   # ciencia publica más lento
PAIR_WINDOW_H = 36       # dos notas solo se unen si se publicaron con <= 36 h de diferencia
SUMMARY_MAX = 400
MAX_STORIES = 30         # por categoría
MIN_OUTLETS = 5          # medios distintos necesarios para que una historia aparezca

CATEGORIES = [
    ("sucesos", "Sucesos"),
    ("politica", "Política"),
    ("finanzas", "Mundo de finanzas"),
    ("mundo", "Mundo"),
    ("ciencias", "Ciencias"),
    ("guerras", "Guerras actuales"),
]

# ---------------------------------------------------------------- filtros
SKIP_PATH = re.compile(
    r"/(opinion|opini%c3%b3n|opinión|commentisfree|editorial|editoriales|tribuna|columnas?|columnistas?|"
    r"blogs?|video|videos|av|audio|podcasts?|programas|programs|sounds|newsletters?|live|en-vivo|"
    r"live-updates|liveblog|deportes|sport|sports|football|futbol|cultura|culture|cine|film|"
    r"television|tv-and-radio|music|musica|gente|estilo|lifestyle|fashion|moda|horoscopo|"
    r"loterias|recetas|food|travel|viajes|games|juegos|crosswords|style|mag|television|"
    r"celebrities|famosos|motor|tecnologia/moviles|gastronomia|agencias|obituaries|obituarios|"
    r"viva|entretenimiento|espectaculos|farandula|tendencias|puro-deporte|deporte|tenis|ocio|planes|"
    r"letters|cartas|reviews|criticas|books)(/|$)",
    re.I,
)
SKIP_TITLE = re.compile(
    r"(^opinion\b|^opinión\b|^editorial\b|^tribuna\b|^an[aá]lisis:|^watch:|^mira:|^video:|^v[ií]deo:|"
    r"^podcast|podcast\b|newsletter|^live\b|\blive:|\blive updates\b|as it happened|en vivo|en directo|"
    r"\|\s*directo|minuto a minuto|última hora de|ultima hora de|latest news bulletin|"
    r"bloomberg this weekend|^the latest:|crossword|horóscopo|horoscopo|^letters:|quiz\b|"
    r"in pictures|en im[aá]genes|fotos:|photos:|^bbc news at|what we know so far|lo que sabemos|^the papers:|"
    r"^firstft:|temblor hoy|[uú]ltimos sismos|sismos? hoy|fin de semana:|mejores planes|planes para|qu[eé] hacer este)",
    re.I,
)
SECTION_TITLE = re.compile(
    r"^(guerra en ucrania|guerra ucrania\s*-?\s*rusia|internacional|portada|econom[ií]a|banca|"
    r"mercados|empresas|bolsa|ahorro|vivienda|fiscal|energ[ií]a)$",
    re.I,
)

WAR = re.compile(
    r"(\b(ucrania|ukraine|kyiv|kiev|odesa|odessa|gaza|ham[aá]s|hezbol[aá]|hezbollah|hut[ií]es|houthis?|"
    r"donbas|donbás|zaporizhzhia|zaporiyia|jarkov|kharkiv|kherson|jers[oó]n|sud[aá]n|rsf|darfur|hormuz|ormuz)\b|"
    r"guerra en|guerra de|war in|war on|iran war|guerra con ir[aá]n|bombardea|bombardeo|airstrike|air strike|"
    r"drone attack|ataques? (rusos|israel[ií]es|con drones|a[eé]reos?)|missile|misil|"
    r"alto el fuego|ceasefire|cease-fire|front-line|front line|frente de batalla|"
    r"\b(rusia|russia|putin)\b.{0,48}\b(guerra|war|ucrania|ukraine|kyiv|kiev|bombar|drone|misil|missile|invasi|refiner)|"
    r"\b(guerra|war|bombar|bombas?|bombs?|strikes?|misil|missile)\b.{0,48}\b(rusia|russia|putin|ucrania|ukraine|iran|ir[aá]n|israel|l[ií]bano|lebanon)|"
    r"\b(israel|israeli|israel[ií]es?)\b.{0,48}\b(strike|attack|ataque|bombard|kill|mata|muert|troops|tropas|soldad|soldier)|"
    r"yemen.{0,30}(war|guerra|houthi|hut[ií]))",
    re.I,
)
SUCESOS = re.compile(
    r"(asesin|murder|homicid|apuñal|stabb|accidente|crash|terremoto|sismo|earthquake|incendio|wildfire|"
    r"\bfire\b|robo |robbery|detenid|arrested|arrest of|injur|herid|collid|colisi|choque|violencia sexual|sexual assault|abuso sexual|"
    r"inundaci|\bflood|desaparecid|missing|violaci[oó]n|\brape\b|v[ií]ctimas?|victims?|killed|\bdead\b|"
    r"muertos|muere\b|mueren\b|fallec|tiroteo|shooting|gunman|pistolero|balacera|secuestr|kidnap|"
    r"explosi[oó]n|explosion|derrumbe|collapse|hurac[aá]n|hurricane|tormenta|storm|tornado|alerta roja|"
    r"rescate|rescue|narco|c[aá]rcel|prison|sentenced|condenad)",
    re.I,
)
SCIENCE = re.compile(
    r"(nasa|esa\b|cient[ií]fic|scientist|\bscience\b|research|investigador|estudio|study|dinosaur|f[ií]sica|"
    r"physics|vacuna|vaccine|starship|\bluna\b|\bmoon\b|\bmarte\b|\bmars\b|gen[eé]tic|genom|\bastronom|"
    r"biolog|nobel|sat[eé]lite|observator|telescop|cambio clim|clim[aá]tic|climate|calentamiento|warming|"
    r"species|especie|oc[eé]ano|ocean|geol[oó]g|c[eé]lula|cell\b|quantum|cu[aá]ntic|fossil|f[oó]sil|"
    r"virus|pandemi|epidemi|\bbrain\b|cerebro|asteroid|\bplanets?\b|planetari|exoplanet|galax|arctic|[aá]rtico|antart|biodivers|"
    r"emisiones|emissions|glaciar|glacier|leap second|segundo intercalar)",
    re.I,
)
POLITICA = re.compile(
    r"(eleccion|election|electoral|partido|party\b|gobierno|government|parlamento|parliament|congreso|"
    r"congress|senado|senate|\bministr|minister|president|\bvoto\b|\bvote|campaña|campaign|primarias|"
    r"primar(y|ies)|trump|lula|milei|petro\b|sheinbaum|maduro|bukele|macron|starmer|merz|s[aá]nchez|"
    r"feij[oó]o|casa blanca|white house|ley\b|\blaw\b|bill\b|proyecto de ley|tribunal supremo|supreme court|"
    r"impeachment|destituci|dimisi|resign|coalici|coalition|referend|diputad|lawmaker|alcald|mayor\b|"
    r"gobernador|governor|oposici|opposition|kast\b|tories|labour|laborista|conservador|conservative|"
    r"republican|dem[oó]crat|pp\b|psoe|vox\b)",
    re.I,
)
FINANZAS = re.compile(
    r"(petr[oó]leo|\boil\b|crudo|mercado|market|bolsa|stocks?\b|shares\b|\bbanc|\bbank|inflaci|inflation|"
    r"\bfed\b|reserva federal|\bbce\b|\becb\b|acciones|investor|inversor|econom|arancel|tariff|\bempleo\b|"
    r"jobs\b|unemploy|desempleo|bonos|\bbonds?\b|\blng\b|deuda|\bdebt\b|wall street|tipos? de inter[eé]s|"
    r"interest rates?|tasas? de inter[eé]s|\bpib\b|\bgdp\b|recesi[oó]n|recession|d[oó]lar|dollar|"
    r"\beuro\b|\boro\b|\bgold\b|bitcoin|cripto|crypto|empresa|company|earnings|beneficios|profit|"
    r"fusi[oó]n|merger|adquisici|acquisition|imf|fmi|presupuesto|budget|impuesto|\btax|salario|wage|"
    r"precios?|prices?|exporta|importa|comercio|trade\b|aerol[ií]nea|airline|inversi[oó]n|investment)",
    re.I,
)
WORLD_PATH = re.compile(r"/(internacional|world|mundo|america|america-latina|am%c3%a9rica-latina|africa|asia|"
                        r"europe|europa|middle[-_]east|oriente|asia-pacific|americas|us-news|eeuu)", re.I)

# ---------------------------------------------------------------- utilidades


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
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def clean_url(url: str) -> str:
    p = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not (k.startswith("utm_") or k.startswith("at_") or k.startswith("syn-")
                 or k in {"mod", "ref", "cmpid", "ns_mchannel", "ns_source", "ns_campaign", "partner", "emc"})]
    return urlunparse(p._replace(query=urlencode(q), fragment=""))


TAG_RE = re.compile(r"<[^>]+>")
TAIL_RE = re.compile(r"(continue reading\.*|the post .* appeared first on .*|leer m[aá]s\.*|"
                     r"seguir leyendo\.*|read more\.*|\[…\]|\[\.\.\.\])\s*$", re.I)


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    txt = unescape(raw)
    txt = TAG_RE.sub(" ", txt)
    txt = unescape(txt)
    txt = " ".join(txt.split())
    txt = TAIL_RE.sub("", txt).strip()
    return txt


def trim(txt: str, limit: int = SUMMARY_MAX) -> str:
    if len(txt) <= limit:
        return txt
    cut = txt[:limit]
    sp = cut.rfind(" ")
    if sp > limit * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:.-—") + "…"


def fetch(url: str, simple: bool = False) -> bytes:
    headers = {"User-Agent": UA}
    if not simple:
        headers["Accept"] = "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
        headers["Accept-Encoding"] = "gzip"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as resp:
        data = resp.read(4_000_000)
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.lstrip(b"\xef\xbb\xbf \t\r\n")


def parse_items(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    found = []
    for it in root.iter():
        if local(it.tag) not in ("item", "entry"):
            continue
        title = link = date_s = desc = ""
        for ch in list(it):
            ln = local(ch.tag)
            if ln == "title" and not title:
                title = clean_text("".join(ch.itertext()))
            elif ln == "link" and not link:
                link = (ch.get("href") or "").strip() or unescape((ch.text or "").strip())
            elif ln in ("pubDate", "date", "published", "updated", "issued") and not date_s:
                date_s = "".join(ch.itertext()).strip()
            elif ln in ("description", "summary", "encoded", "content") and len(desc) < 40:
                d = clean_text("".join(ch.itertext()))
                if len(d) > len(desc):
                    desc = d
            elif ln == "group":  # media:group > media:description
                for g in ch:
                    if local(g.tag) == "description" and len(desc) < 40:
                        desc = clean_text("".join(g.itertext()))
        if title and link:
            found.append((title, link, date_s, desc))
    if not found:
        # Sitemap de noticias de Google (<url><loc> + <news:title>, <news:publication_date>),
        # para medios sin RSS (p. ej. CRHoy, Trivisión).
        for u in root.iter():
            if local(u.tag) != "url":
                continue
            title = link = date_s = ""
            for ch in u.iter():
                ln = local(ch.tag)
                if ln == "loc" and not link:
                    link = (ch.text or "").strip()
                elif ln == "title" and not title:
                    title = clean_text("".join(ch.itertext()))
                elif ln == "publication_date" and not date_s:
                    date_s = (ch.text or "").strip()
            if title and link:
                found.append((title, link, date_s, ""))
    return found


def fetch_feed(feed):
    fid, url = feed[0], feed[1]
    err = None
    for attempt in range(2):  # un reintento con cabeceras mínimas
        try:
            return feed, parse_items(fetch(url, simple=attempt > 0)), None
        except Exception as exc:
            err = f"{type(exc).__name__}: {str(exc)[:160]}"
            time.sleep(2)
    return feed, None, err


# ---------------------------------------------------------------- clasificación


def classify(title: str, summary: str, hint: str | None, path: str) -> str | None:
    t = title
    if WAR.search(t):
        return "guerras"
    if hint == "guerras":
        return "guerras"
    sci_path = bool(re.search(r"/(science|ciencia|ciencias|environment|medio-ambiente|clima|salud|health)(/|-|$)", path))
    if hint == "ciencias":
        return "ciencias" if (SCIENCE.search(t) or SCIENCE.search(summary[:200]) or sci_path) else None
    if sci_path and SCIENCE.search(t + " " + summary[:200]):
        return "ciencias"
    if SUCESOS.search(t):
        return "sucesos"
    pol, fin = bool(POLITICA.search(t)), bool(FINANZAS.search(t))
    if hint == "finanzas":
        return "politica" if (pol and not fin) else "finanzas"
    if hint == "politica":
        return "finanzas" if (fin and not pol) else "politica"
    if SCIENCE.search(t) and ("/science" in path or "/ciencia" in path or "/environment" in path or "/clima" in path):
        return "ciencias"
    if FINANZAS.search(t) or re.search(r"/(econom|business|markets|finanzas|negocios|dinero|mercados)", path):
        return "finanzas"
    if POLITICA.search(t) or re.search(r"/(politica|politics|espana/|nacional)", path):
        return "politica"
    if hint == "mundo" or WORLD_PATH.search(path):
        return "mundo"
    if SCIENCE.search(t):
        return "ciencias"
    return "mundo" if hint is None else hint


# ---------------------------------------------------------------- texto -> términos

_PHRASE_RE = [(re.compile(r"\b" + re.escape(a) + r"(?=\W|$)"), " " + b + " ") for a, b in PHRASES]


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def terms(text: str) -> list[str]:
    # Siglas sensibles a mayúsculas antes de pasar a minúsculas.
    text = re.sub(r"\bU\.?S\.?A?\b(?!\w)", " usa ", text)
    text = re.sub(r"\bUN\b", " unorg ", text)
    text = re.sub(r"\bUK\b", " uk ", text)
    text = re.sub(r"\b(EU|UE)\b", " eu ", text)
    text = re.sub(r"\bONU\b", " unorg ", text)
    t = fold(text).lower()
    t = t.replace("’", "'").replace("‘", "'")
    t = re.sub(r"'s\b", "", t)
    for rx, rep in _PHRASE_RE:
        t = rx.sub(rep, t)
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        if w.isdigit():
            if len(w) >= 2 and not (1990 <= int(w) <= 2035):
                out.append("#" + w)
            continue
        w = WORDS.get(w, w)
        if w in STOP or len(w) < 3:
            continue
        for part in w.split():
            out.append(part[:6])
    return out


# ---------------------------------------------------------------- agrupación


class DSU:
    def __init__(self, n):
        self.p = list(range(n))
        self.members = {i: [i] for i in range(n)}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if len(self.members[ra]) < len(self.members[rb]):
            ra, rb = rb, ra
        self.p[rb] = ra
        self.members[ra].extend(self.members.pop(rb))
        return ra


def build_vectors(items):
    docs = []
    for it in items:
        tt = terms(it["title"])
        st = terms(it["summary"][:300]) if it["summary"] else []
        it["_tt"] = set(tt)
        it["_all"] = set(tt) | set(st)
        tf = Counter()
        for w in tt:
            tf[w] += 2.0
        for w in st:
            tf[w] += 1.0
        docs.append(tf)
    n = len(docs)
    df = Counter()
    for it in items:
        df.update(it["_all"])
    idf = {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}
    for it, tf in zip(items, docs):
        vec = {w: (1 + math.log(c)) * idf[w] for w, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        it["_vec"] = {w: v / norm for w, v in vec.items()}
    return idf, df


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(w, 0.0) for w, v in a.items())


def cluster(items, idf, df, n_ref=None):
    """n_ref: tamaño del corpus con el que se calcularon idf/df (si es mayor que items)."""
    n = len(items)
    N = n_ref or n
    rare_cut = math.log((N + 1) / (max(4, N * 0.012) + 0.5))   # término "distintivo"
    common_cut = N * 0.06
    index = defaultdict(list)
    for i, it in enumerate(items):
        for w in it["_all"]:
            if df[w] <= common_cut:
                index[w].append(i)
    cand = set()
    for w, lst in index.items():
        if len(lst) > 400:
            continue
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                cand.add((lst[a], lst[b]))

    sims = {}
    pairs = []
    for i, j in cand:
        a, b = items[i], items[j]
        if abs(a["_ts"] - b["_ts"]) > PAIR_WINDOW_H * 3600:
            continue
        s = cos(a["_vec"], b["_vec"])
        if s < 0.12:
            continue
        shared_title = a["_tt"] & b["_tt"]
        shared = a["_all"] & b["_all"]
        rare = [w for w in shared if idf.get(w, 0) >= rare_cut]
        rare_title = [w for w in shared_title if idf.get(w, 0) >= rare_cut]
        cross = a["lang"] != b["lang"]
        # Reglas de enlace: similitud alta + al menos 2 términos distintivos en común,
        # y que al menos uno de ellos esté en los dos titulares.
        need = 0.30 if cross else 0.36
        ok = (s >= need and len(rare) >= 2 and len(rare_title) >= 1) or \
             (s >= 0.55 and len(rare) >= 1 and len(shared_title) >= 2)
        sims[(i, j)] = s
        if ok:
            pairs.append((s, i, j))
    pairs.sort(reverse=True)

    def sim(i, j):
        if i > j:
            i, j = j, i
        v = sims.get((i, j))
        if v is None:
            v = cos(items[i]["_vec"], items[j]["_vec"])
            sims[(i, j)] = v
        return v

    dsu = DSU(n)
    AVG_MIN = 0.20
    for s, i, j in pairs:
        ri, rj = dsu.find(i), dsu.find(j)
        if ri == rj:
            continue
        A, B = dsu.members[ri], dsu.members[rj]
        ts = [items[k]["_ts"] for k in A + B]
        if max(ts) - min(ts) > 60 * 3600:
            continue
        tot = 0.0
        for x in A:
            for y in B:
                tot += sim(x, y)
        if tot / (len(A) * len(B)) < AVG_MIN:
            continue
        dsu.union(i, j)
    groups = [m for m in dsu.members.values()]
    return groups, sims


# ---------------------------------------------------------------- principal


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_cron(now: datetime) -> datetime:
    base = now.replace(minute=0, second=0, microsecond=0)
    h = (base.hour // REFRESH_HOURS + 1) * REFRESH_HOURS
    return base.replace(hour=0) + timedelta(hours=h)


def make_story(g, pool, sims):
    """Arma la tarjeta de un grupo: titular y resumen por idioma (el más central), medios y fuentes."""
    members = [pool[i] for i in g]
    orgs = {m["org"] for m in members}

    def centrality(i):
        return sum(sims.get((min(i, j), max(i, j)), 0.0) for j in g if j != i)
    by_lang = {}
    for lang in ("es", "en"):
        cands = [i for i in g if pool[i]["lang"] == lang]
        if cands:
            cands.sort(key=lambda i: (centrality(i), len(pool[i]["summary"]) > 60), reverse=True)
            by_lang[lang] = cands

    def best_summary(lang):
        for i in by_lang.get(lang, []):
            if len(pool[i]["summary"]) >= 60:
                return pool[i]["summary"], pool[i]["source"]
        return None, None

    ts = [m["_ts"] for m in members]
    es_sum, es_src = best_summary("es")
    en_sum, en_src = best_summary("en")
    head_es = pool[by_lang["es"][0]]["title"] if "es" in by_lang else None
    head_en = pool[by_lang["en"][0]]["title"] if "en" in by_lang else None
    sources = []
    for m in sorted(members, key=lambda m: m["_ts"]):
        sources.append({"source": m["source"], "lang": m["lang"], "title": m["title"],
                        "url": m["url"], "publishedAt": m["publishedAt"]})
    return {
        "headline": head_es or head_en,
        "headlineLang": "es" if head_es else "en",
        "headlineEs": head_es,
        "headlineEn": head_en,
        "summaryEs": es_sum, "summaryEsSource": es_src,
        "summaryEn": en_sum, "summaryEnSource": en_src,
        "outlets": len(orgs),
        "outletNames": sorted({m["source"].replace(" Español", "").replace(" English", "") for m in members}),
        "languages": sorted({m["lang"] for m in members}),
        "firstSeen": iso(min(ts)), "lastSeen": iso(max(ts)),
        "sources": sources,
        "_last": max(ts),
    }


POSIBLES_MAX = 60          # tope total de la pestaña "Posibles noticias"
POSIBLES_PER_CHIP = 8      # tope por categoría/región
POSIBLES_MIN_PER_CHIP = 3  # se reservan hasta 3 por categoría/región para que no las tapen otras
POSIBLES_MIN_CHIP = {"cripto": 6}  # Criptomonedas tiene 6 lugares asegurados


def build_posibles(candidates, out_cats, region_labels):
    """Grupos con 2-4 medios distintos que no están en ninguna pestaña de consenso (5+).
    Se descarta cualquier grupo que comparta una nota con una historia ya confirmada, y los
    grupos repetidos entre el corpus general, el regional y el cripto se fusionan (se queda el
    de más medios y se juntan las etiquetas de categoría/región)."""
    cat_labels = dict(CATEGORIES) | {"cripto": "Criptomonedas"}
    confirmed = {src["url"] for c in out_cats if c["id"] not in ("buenas", "posibles")
                 for s in c["stories"] for src in s["sources"]}
    kept = []
    for c in sorted(candidates, key=lambda s: (s["outlets"], bool(s.get("region")), s["_last"]), reverse=True):
        urls = {src["url"] for src in c["sources"]}
        if urls & confirmed:
            continue
        chips = []
        if c.get("category") in cat_labels:
            chips.append(c["category"])
        if c.get("region") in region_labels:
            chips.append(c["region"])
        dup = next((k for k in kept if urls & k["_urls"]), None)
        if dup:
            for ch in chips:
                if ch not in dup["_chips"]:
                    dup["_chips"].append(ch)
            continue
        c["_urls"], c["_chips"] = urls, chips
        kept.append(c)

    def main_chip(c):
        # Las regiones mandan para el tope: así Costa Rica o Centroamérica no quedan tapadas.
        regs = [ch for ch in c["_chips"] if ch in region_labels]
        return regs[0] if regs else (c["_chips"][0] if c["_chips"] else "otros")

    order = sorted(kept, key=lambda s: (s["outlets"], s["_last"]), reverse=True)
    chosen, per = [], Counter()
    for c in order:                      # 1) reserva mínima por categoría/región
        if per[main_chip(c)] < POSIBLES_MIN_CHIP.get(main_chip(c), POSIBLES_MIN_PER_CHIP):
            chosen.append(c)
            per[main_chip(c)] += 1
    for c in order:                      # 2) relleno por medios y recencia, con tope por etiqueta
        if len(chosen) >= POSIBLES_MAX:
            break
        if c not in chosen and per[main_chip(c)] < POSIBLES_PER_CHIP:
            chosen.append(c)
            per[main_chip(c)] += 1
    chosen.sort(key=lambda s: (s["outlets"], s["_last"]), reverse=True)
    chosen = chosen[:POSIBLES_MAX]
    out = []
    for i, c in enumerate(chosen):
        c["chips"] = [{"id": ch, "label": cat_labels.get(ch) or region_labels.get(ch)} for ch in c["_chips"]]
        for k in ("_urls", "_chips", "_last", "category", "region"):
            c.pop(k, None)
        c["id"] = f"posibles-{i + 1}"
        out.append(c)
    report = {"candidates": len(candidates), "afterDedupe": len(kept), "shown": len(out),
              "byOutlets": dict(sorted(Counter(c["outlets"] for c in out).items())),
              "byChip": dict(Counter(ch["id"] for c in out for ch in c["chips"]))}
    return out, report


# Orden de pestañas pedido: Buenas, Costa Rica, Finanzas, Política, Cripto, Sucesos y luego el resto
# (Mundo, Ciencias, Guerras, regiones, Posibles) en su orden actual.
TAB_FIRST = ["buenas", "costarica", "finanzas", "politica", "cripto", "sucesos"]


def order_tabs(cats):
    first = [c for t in TAB_FIRST for c in cats if c["id"] == t]
    return first + [c for c in cats if c["id"] not in TAB_FIRST]


def main():
    now = datetime.now(timezone.utc)
    ok_feeds, failed = [], []
    pool, seen = [], set()

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(fetch_feed, FEEDS))

    for feed, rows, err in results:
        fid, url, source, org, lang, hint = feed
        if err or not rows:
            failed.append({"id": fid, "source": source, "url": url, "error": err or "sin ítems"})
            print(f"FAIL {fid}: {err or 'empty'}")
            continue
        kept = 0
        newest = None
        for title, link, date_s, desc in rows:
            if len(title) < 18 or SKIP_TITLE.search(title) or SECTION_TITLE.search(title):
                continue
            url_c = clean_url(link)
            if not url_c.startswith("http"):
                continue
            path = urlparse(url_c).path.lower()
            if SKIP_PATH.search(path):
                continue
            published = parse_date(date_s)
            if published is None or published > now + timedelta(hours=3):
                continue
            hours = SCIENCE_HOURS if hint == "ciencias" else NEWS_HOURS
            if published < now - timedelta(hours=hours):
                continue
            summary = desc
            if summary and fold(summary.lower())[:60] == fold(title.lower())[:60]:
                summary = ""  # el resumen solo repite el titular
            cat = classify(title, summary, hint, path)
            if not cat:
                continue
            key = (urlparse(url_c).netloc.replace("www.", "") + urlparse(url_c).path.rstrip("/")).lower()
            tkey = org + "|" + re.sub(r"\W+", "", fold(title.lower()))[:90]
            if key in seen or tkey in seen:
                continue
            seen.add(key)
            seen.add(tkey)
            pool.append({
                "title": title, "url": url_c, "source": source, "org": org, "lang": lang,
                "summary": trim(summary), "category": cat, "feed": fid,
                "publishedAt": published.strftime("%Y-%m-%dT%H:%M:%SZ"), "_ts": published.timestamp(),
            })
            kept += 1
            newest = published if newest is None or published > newest else newest
        ok_feeds.append({"id": fid, "source": source, "lang": lang, "url": url, "itemsInFeed": len(rows),
                         "kept": kept, "newest": newest.strftime("%Y-%m-%dT%H:%M:%SZ") if newest else None})
        print(f"OK   {fid:22s} raw={len(rows):3d} kept={kept}")

    for fid, url, reason in KNOWN_FAILS:
        failed.append({"id": fid, "source": fid, "url": url, "error": reason})

    print(f"\nitems={len(pool)}")
    idf, df = build_vectors(pool)
    groups, sims = cluster(pool, idf, df)

    stories_by_cat = defaultdict(list)
    candidates = []          # grupos de 2-4 medios: van a "Posibles noticias"
    debug_rows = []
    for g in groups:
        members = [pool[i] for i in g]
        orgs = {m["org"] for m in members}
        if len(orgs) < 2:
            continue
        story = make_story(g, pool, sims)
        # Categoría por votos; "guerras" y "sucesos" ganan empates porque son más específicas.
        votes = Counter(m["category"] for m in members)
        prio = {"guerras": 6, "sucesos": 5, "ciencias": 4, "finanzas": 3, "politica": 2, "mundo": 1}
        cat = max(votes, key=lambda c: (votes[c], prio[c]))
        if votes.get("guerras", 0) * 3 >= len(members) and cat != "guerras":
            cat = "guerras"
        debug_rows.append((cat, len(orgs), members))
        if len(orgs) < MIN_OUTLETS:
            story["category"] = cat
            candidates.append(story)
            continue
        stories_by_cat[cat].append(story)

    crypto_report = None
    out_cats = []
    summary_counts = {}
    for cid, label in CATEGORIES:
        lst = stories_by_cat.get(cid, [])
        lst.sort(key=lambda s: (s["outlets"], s["_last"]), reverse=True)
        lst = lst[:MAX_STORIES]
        for i, s in enumerate(lst):
            s.pop("_last", None)
            s["id"] = f"{cid}-{i + 1}"
        summary_counts[cid] = len(lst)
        out_cats.append({"id": cid, "label": label, "minOutlets": MIN_OUTLETS, "stories": lst})
        if cid == "finanzas":
            # Pestaña "Criptomonedas": solo historias con 5+ medios distintos (ver cripto.py).
            try:
                import cripto
                crypto_stories, crypto_report, crypto_debug = cripto.build(now, pool)
                for c in crypto_report.pop("_candidates", []):
                    c["category"] = "cripto"
                    candidates.append(c)
                out_cats.append({"id": "cripto", "label": "Criptomonedas", "minOutlets": cripto.MIN_OUTLETS,
                                 "stories": crypto_stories})
                summary_counts["cripto"] = len(crypto_stories)
                print("cripto", crypto_report["itemsGathered"], "notas,", crypto_report["groupsByOutletCount"])
                if DEBUG:
                    with open(ROOT / "debug_cripto.txt", "w", encoding="utf-8") as fh:
                        for k, members in sorted(crypto_debug, key=lambda r: -r[0]):
                            fh.write(f"\n=== {k} medios\n")
                            for m in sorted(members, key=lambda m: m["org"]):
                                fh.write(f"  {m['lang']} {m['source'][:16]:16s} {m['publishedAt'][5:16]} {m['title'][:105]}\n")
            except Exception as exc:  # nunca romper la actualización principal
                crypto_report = {"error": f"{type(exc).__name__}: {exc}"}
                print("cripto FAIL", type(exc).__name__, exc)

    # Pestañas regionales: 5+ medios distintos, región por lugares nombrados (ver regiones.py).
    region_report = None
    region_labels = {}
    try:
        import regiones
        reg_cats, region_report, reg_debug = regiones.build(now, pool, {f[1] for f in FEEDS})
        candidates.extend(region_report.pop("_candidates", []))
        region_labels = dict(regiones.REGIONS)
        out_cats.extend(reg_cats)
        for c in reg_cats:
            summary_counts[c["id"]] = len(c["stories"])
        print("regiones", region_report["perRegion"], "medios locales", region_report["workingLocalOutletsPerRegion"])
        if DEBUG:
            with open(ROOT / "debug_regiones.txt", "w", encoding="utf-8") as fh:
                for r, k, members in sorted(reg_debug, key=lambda x: (x[0], -x[1])):
                    fh.write(f"\n=== [{r}] {k} medios\n")
                    for m in sorted(members, key=lambda m: m["org"]):
                        fh.write(f"  {m['lang']} {m['source'][:18]:18s} {m['title'][:105]}\n")
    except Exception as exc:  # nunca romper la actualización principal
        region_report = {"error": f"{type(exc).__name__}: {exc}"}
        print("regiones FAIL", type(exc).__name__, exc)

    # Pestaña "Posibles noticias": grupos de 2-4 medios distintos que NO llegaron a 5.
    try:
        posibles, posibles_report = build_posibles(candidates, out_cats, region_labels)
        out_cats.append({"id": "posibles", "label": "Posibles noticias", "minOutlets": 2,
                         "maxOutlets": MIN_OUTLETS - 1, "stories": posibles})
        summary_counts["posibles"] = len(posibles)
        print("posibles", posibles_report)
    except Exception as exc:
        posibles_report = {"error": f"{type(exc).__name__}: {exc}"}
        print("posibles FAIL", type(exc).__name__, exc)

    # Pestaña "Buenas noticias": basta 1 fuente confiable (ver buenas.py).
    good_report = None
    try:
        import buenas
        good, good_report = buenas.build(now, pool, FEEDS)
        out_cats.append({"id": "buenas", "label": "Buenas noticias", "minOutlets": 1, "stories": good})
        summary_counts["buenas"] = len(good)
        print("buenas", good_report["perSubtopic"], "leads", good_report["leads"]["confirmed"], "/", good_report["leads"]["total"])
    except Exception as exc:  # nunca romper la actualización principal
        print("buenas FAIL", type(exc).__name__, exc)

    payload = {
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nextRefreshAt": next_cron(now).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "refreshHours": REFRESH_HOURS,
        "method": {
            "minOutlets": MIN_OUTLETS,
            "pairWindowHours": PAIR_WINDOW_H,
            "newsMaxAgeHours": NEWS_HOURS,
            "description": "Agrupación por TF-IDF y términos distintivos comunes (ES/EN), solo grupos con 5+ medios distintos.",
        },
        "stats": {
            "feedsOk": len(ok_feeds),
            "feedsFailed": len([f for f in failed]),
            "itemsGathered": len(pool),
            "clusters": len(groups),
            "consensusStories": sum(v for k, v in summary_counts.items() if k in ("sucesos", "politica", "finanzas", "mundo", "ciencias", "guerras")),
            "perCategory": summary_counts,
        },
        "sourcesUsed": sorted({f["source"] for f in ok_feeds if f["kept"] > 0}),
        "categories": order_tabs(out_cats),
        "feedsOk": ok_feeds,
        "feedsFailed": failed,
        "goodNews": good_report,
        "crypto": crypto_report,
        "regions": region_report,
        "possible": posibles_report,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("clusters", len(groups), "consensus", summary_counts)

    if DEBUG:
        with open(ROOT / "debug_clusters.txt", "w", encoding="utf-8") as fh:
            for cat, k, members in sorted(debug_rows, key=lambda r: (-r[1], r[0])):
                fh.write(f"\n=== [{cat}] {k} medios\n")
                for m in sorted(members, key=lambda m: m["org"]):
                    fh.write(f"  {m['lang']} {m['source'][:18]:18s} {m['title'][:110]}\n")


if __name__ == "__main__":
    main()
