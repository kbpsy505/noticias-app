#!/usr/bin/env python3
"""Briefing de consenso: agrupación solo con código; el relato de cada historia lo escribe una IA
o, sin clave, se arma con frases de varios medios (narrar.py).

1. Descarga RSS públicos (feeds.py).
2. Normaliza títulos y resúmenes en español e inglés a un vocabulario común.
3. Agrupa notas sobre el mismo hecho (TF-IDF + coincidencia de términos
   distintivos + ventana de tiempo), aunque estén en idiomas distintos.
4. Conserva solo los grupos que publican 3 o más medios distintos (MIN_OUTLETS).
5. Relato de cada historia (narrar.py): IA vía cualquier API compatible con OpenAI (xAI por omisión,
   Gemini, Groq…) con todas sus notas; sin clave o si falla, extracto de frases de varios medios.
6. Escribe noticias.json para la página.

Titulares y fuentes salen tal cual de cada feed; el relato lo escribe la IA solo con esos textos.
"""
from __future__ import annotations

import gzip
import zlib
import json
import math
import os
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

import enlaces
from feeds import FEEDS, KNOWN_FAILS, WEEKLY_FEEDS
from vocab import PHRASES, STOP, WORDS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "noticias.json"
DEBUG = "--debug" in sys.argv
REFRESH_HOURS = 3
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

PHASE = 4                # fase del plan de mejoras de contenido aplicada en esta rama (pruebas)
NEWS_HOURS = 48          # antigüedad máxima de una nota (noticias)
SCIENCE_HOURS = 24 * 7   # ciencia publica más lento
PAIR_WINDOW_H = 36       # dos notas solo se unen si se publicaron con <= 36 h de diferencia
SUMMARY_MAX = 400
MAX_STORIES = 30         # por categoría
MIN_OUTLETS = 3          # medios distintos necesarios para que una historia aparezca
FROZEN_HOURS = 72        # un feed cuya nota más nueva tiene más de 72 h se marca «congelado» (salvo semanales)
WEEKLY_HOURS = 24 * 10   # tope de «congelado» para los feeds semanales

CATEGORIES = [
    ("sucesos", "Sucesos"),
    ("politica", "Política"),
    ("finanzas", "Mundo de finanzas"),
    ("mundo", "Mundo"),
    ("ciencias", "Ciencias"),
    ("guerras", "Guerras y conflictos"),
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
    r"^firstft:|temblor hoy|[uú]ltimos sismos|sismos? hoy|fin de semana:|mejores planes|planes para|qu[eé] hacer este|"
    # Notas de servicio que se repiten con otro país o sorteo (con 3 medios se agrupaban entre sí).
    r"^temblor en [^:]{2,30}( hoy|: (sismos|hora|epicentro|lugar|[uú]ltimo))|sismos recientes|loter[ií]a nacional: est|n[uú]meros ganadores|resultados del (sorteo|tris|chispazo|gana diario|progol|melate)|"
    r"^sorteo mayor|^progol|qu[eé] est[aá] pasando en el metro|pron[oó]stico del tiempo:|"
    # Cotización diaria del dólar (se repite cada día y por país).
    r"precio del d[oó]lar\b.{0,30}\bhoy\b|precio del d[oó]lar (hoy|en )|d[oó]lar (blue |oficial |estadounidense )?hoy\b|tipo de cambio (del d[oó]lar )?(hoy|para este)|casas de cambio: precio)",
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
# Presupuesto y gasto público: es política (Corte, Asamblea, Gobierno), no mercados. Va a Política
# salvo que el titular hable también de mercados o economía en sentido estricto.
PUBLIC_BUDGET = re.compile(
    r"(presupuest|budget|recortes?\b|\bcuts?\b|fondos? (p[uú]blicos|para|de vivienda|del estado)|gasto p[uú]blico|"
    r"public spending|financiamiento (de|para) (la|las|los|el)|\bfees\b|transferencias?\b|partidas?\b)",
    re.I,
)
GOV_ACTOR = re.compile(
    r"(poder judicial|\bcorte\b|sala iv|sala constitucional|asamblea|diputad|congres|parlament|senad|gobierno|"
    r"government|ministr|universidad|\bucr\b|\btec\b|municipal|alcald|contralor|hacienda|chaves|"
    r"s[aá]nchez|presiden|\bcaja\b|ccss|\bmep\b|\boij\b|fiscal[ií]a|tribunal|38 votos|votos)",
    re.I,
)
MARKET_CORE = re.compile(
    r"(bolsa|stocks?\b|shares\b|wall street|inflaci|inflation|\bfed\b|reserva federal|\bbccr\b|banco central|"
    r"tipos? de inter[eé]s|tasas? de inter[eé]s|interest rates?|\bpib\b|\bgdp\b|recesi|recession|arancel|tariff|"
    r"d[oó]lar|dollar|earnings|bonos|\bbonds?\b|petr[oó]leo|\boil\b|mercados?\b|markets?\b|\bfmi\b|\bimf\b|"
    r"calificaci[oó]n|rating|deuda soberana|eurobonos)",
    re.I,
)


def budget_politics(t: str) -> bool:
    return bool(PUBLIC_BUDGET.search(t) and GOV_ACTOR.search(t) and not MARKET_CORE.search(t))


# Notas que nombran un país en guerra pero no son de la guerra (deportaciones, deporte, cultura).
NON_WAR = re.compile(
    r"(deport|migrant|inmigra|immigra|refugee status|protected status|\btps\b|asylum|asilo|visa|"
    r"tennis|tenis|davis cup|copa davis|\bcup\b|\bcopa\b|\bwta\b|\batp\b|open\b|torneo|tournament|f[uú]tbol|football|soccer|champions|mundial|"
    r"world cup|olymp|ol[ií]mpic|eurovisi|festival|film|pel[ií]cula|museo|museum|concierto|concert|"
    r"\bmatch\b|partido de|semifinal|final\b|cuartos de final|quarter-?final|beat[s]?\b|vence|derrota a)",
    re.I,
)
HARD_WAR = re.compile(
    r"(bombard|bombs?\b|bombas?\b|missile|misil|airstrike|air strike|strikes? on|ataques? (rus|israel|a[eé]re|con dron)|"
    r"drone attack|drones? (rus|ucran|attack)|killed|kills|muert|mata\b|matan\b|troops|tropas|ofensiva|offensive|"
    r"shelling|front ?line|frente de batalla|invasi|ceasefire|cease-fire|alto el fuego|peace talks|negociaciones de paz)",
    re.I,
)


def war_story(t: str) -> bool:
    """Señal real de guerra: el patrón WAR, sin ser una nota de migración/deporte/cultura
    (salvo que también traiga términos duros de guerra)."""
    if not WAR.search(t):
        return False
    return not NON_WAR.search(t) or bool(HARD_WAR.search(t))


FINANZAS = re.compile(
    r"(petr[oó]leo|\boil\b|crudo|mercado|market|bolsa|stocks?\b|shares\b|\bbanc|(?<!west )\bbank|inflaci|inflation|"
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


_ISO_TZ_FIX = re.compile(r"T?Z$")


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
    # ISO 8601 con espacios o saltos de línea dentro (science.org: «2026-11-16\nT02:15:00\nZ») o «…TZ».
    iso = re.sub(r"\s+", "", raw)
    iso = _ISO_TZ_FIX.sub("Z", iso)
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
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


FETCH_TIMEOUT = 25
MAX_DOWNLOAD = 4_000_000
MAX_DECOMPRESSED = 20_000_000
CURL_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
GN_TITLE_SUFFIX = re.compile(r"\s+[-|–]\s+[^-|–]{2,45}$")


def fetch(url: str, simple: bool = False) -> bytes:
    headers = {"User-Agent": UA}
    if not simple:
        headers["Accept"] = "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
        headers["Accept-Encoding"] = "gzip"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT, context=ssl.create_default_context()) as resp:
        data = resp.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("respuesta demasiado grande")
    if data[:2] == b"\x1f\x8b":
        data = gunzip_capped(data)
    return data.lstrip(b"\xef\xbb\xbf \t\r\n")


def gunzip_capped(data: bytes, limit: int | None = None) -> bytes:
    """Descomprime gzip con tope de salida (evita gzip bombs)."""
    limit = MAX_DECOMPRESSED if limit is None else limit
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(data, limit + 1)
    if len(out) > limit or d.unconsumed_tail:
        raise ValueError("gzip descomprimido supera el tope")
    return out


# Un DOCTYPE simple (sin subconjunto interno) es inofensivo para ElementTree; se rechazan
# las declaraciones de entidades y los DOCTYPE con subconjunto interno [ ... ].
_DTD_RE = re.compile(rb"<!ENTITY|<!DOCTYPE[^>\[]*\[", re.I)


def safe_fromstring(xml_bytes: bytes):
    """Parsea XML rechazando ENTITY y DOCTYPE con subconjunto interno (sin XXE ni expansión de entidades)."""
    if _DTD_RE.search(xml_bytes[:MAX_DECOMPRESSED]):
        raise ValueError("XML con DOCTYPE/ENTITY rechazado")
    return ET.fromstring(xml_bytes)


def is_safe_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.hostname) and url.startswith(p.scheme + "://")


def parse_items(xml_bytes: bytes):
    root = safe_fromstring(xml_bytes)
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
    """Descarga y parsea un feed; los ítems de feeds directos (no Google) alimentan el índice de titulares
    que sirve para cambiar enlaces de Google Noticias por el enlace real del medio (enlaces.py)."""
    res = _fetch_feed(feed)
    if res[1] and not enlaces.is_gn(feed[1]):
        enlaces.index_items(res[1])
    return res


def _fetch_feed(feed):
    fid, url = feed[0], feed[1]
    err = None
    for attempt in range(2):  # un reintento con cabeceras mínimas
        try:
            return feed, parse_items(fetch(url, simple=attempt > 0)), None
        except Exception as exc:
            err = f"{type(exc).__name__}: {str(exc)[:160]}"
            time.sleep(2)
    # Último intento con curl --compressed: algunos sitios (p. ej. Tico Times) responden en brotli
    # aunque se pida gzip, o rechazan a urllib (PBS); curl sí los lee desde GitHub Actions.
    try:
        import subprocess
        if not is_safe_http_url(url):
            return feed, None, err
        data = subprocess.run(["curl", "-sL", "--proto", "=http,https", "--max-redirs", "5",
                               "-m", str(FETCH_TIMEOUT), "--max-filesize", str(MAX_DOWNLOAD),
                               "--compressed", "-A", CURL_UA, url],
                              capture_output=True, timeout=FETCH_TIMEOUT + 5).stdout
        if len(data) > MAX_DECOMPRESSED:
            raise ValueError("respuesta curl demasiado grande")
        rows = parse_items(data.lstrip(b"\xef\xbb\xbf \t\r\n"))
        if rows:
            return feed, rows, None
    except Exception:
        pass
    return feed, None, err


def frozen_reason(fid: str, raw_newest, now) -> str | None:
    """Motivo «congelado» si el feed trae ítems pero ninguno con fecha legible o reciente (Arreglo 5)."""
    if raw_newest is None:
        return "congelado: ninguna fecha legible en el feed"
    limit = WEEKLY_HOURS if fid in WEEKLY_FEEDS else FROZEN_HOURS
    age = (now - raw_newest).total_seconds() / 3600
    if age > limit:
        return f"congelado: la nota más nueva tiene {age / 24:.0f} días"
    return None


# ---------------------------------------------------------------- clasificación


def classify(title: str, summary: str, hint: str | None, path: str) -> str | None:
    t = title
    if war_story(t):
        return "guerras"
    if hint == "guerras" and not (NON_WAR.search(t) and not HARD_WAR.search(t)):
        return "guerras"
    sci_path = bool(re.search(r"/(science|ciencia|ciencias|environment|medio-ambiente|clima|salud|health)(/|-|$)", path))
    if hint == "ciencias":
        return "ciencias" if (SCIENCE.search(t) or SCIENCE.search(summary[:200]) or sci_path) else None
    if sci_path and SCIENCE.search(t + " " + summary[:200]):
        return "ciencias"
    if SUCESOS.search(t):
        return "sucesos"
    if budget_politics(t):
        return "politica"
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


_NOT_NAMES = set("""january february march april may june july august september october november december
enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre
monday tuesday wednesday thursday friday saturday sunday lunes martes miercoles jueves viernes sabado domingo""".split())


def title_names(title: str, lower: set | None = None) -> set[str]:
    """Nombres propios del titular (palabras con mayúscula, siglas), en forma de término.
    Incluye la primera palabra (en «Salomon abre su primera tienda» la marca va al inicio), pero
    no los términos que en otros titulares aparecen en minúscula («Temblor», «Corte», «Launches»)."""
    words = re.findall(r"[\w’'&]+", title)
    longw = [w for w in words if len(w) >= 4 and not w.isupper()]
    # Titulares en «Title Case» (WSJ, Bloomberg): todas las palabras van con mayúscula, no se distinguen nombres.
    if len(longw) >= 4 and sum(w[0].isupper() for w in longw) >= 0.7 * len(longw):
        return set()
    def skip(w):
        return fold(w).lower() in _NOT_NAMES or bool(lower and w.lower() in lower)

    # Rachas de palabras con mayúscula («Rob Jetten», «Países Bajos»): se pasan juntas a términos para
    # que las frases del vocabulario se apliquen («Países Bajos» -> netherlands).
    runs, cur = [], []
    for w in words:
        if w[:1].isupper():
            cur.append(w)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    out = set()
    for run in runs:
        keep = [w for w in run if not skip(w) and (len(w) >= 3 or len(run) > 1)]
        if not keep:
            continue
        drop = set()
        for w in run:
            if skip(w):
                drop.update(terms(w))
        out.update(t for t in terms(" ".join(run)) if t not in drop)
    return out


def lowercase_terms(items) -> set:
    """Palabras (completas) que aparecen escritas en minúscula en algún titular: no son nombres propios."""
    low = set()
    for it in items:
        for w in re.findall(r"[\w’'&]+", it["title"])[1:]:
            if w[:1].islower():
                low.add(w)
    return low


# Países (texto plegado, minúsculas) -> código. Dos titulares de países distintos que no se nombran
# entre sí cuentan como hechos distintos («temblor en Guatemala» ≠ «temblor en Costa Rica»).
_COUNTRIES = {
    "cr": r"costa rica|costarricens\w*", "gt": r"guatemal\w*", "hn": r"hondur\w*", "sv": r"el salvador|salvadoren\w*",
    "ni": r"nicaragu\w*", "pa": r"panam[ae]\w*", "mx": r"mexic\w*|mejic\w*", "cu": r"cuba\w*", "co": r"colombia\w*",
    "ve": r"venezuel\w*", "ec": r"ecuador\w*", "pe": r"peru\w*", "cl": r"chile\w*", "ar": r"argentin\w*",
    "bo": r"bolivia\w*", "py": r"paraguay\w*", "uy": r"uruguay\w*", "br": r"brasil\w*|brazil\w*",
    "do": r"republica dominicana|dominican\w*", "es": r"espana|spain|spanish",
    "jp": r"japon\w*|japan\w*", "cn": r"china|chinese|chin[oa]s", "in": r"india|indian", "ph": r"filipin\w*|philippin\w*",
    "id": r"indonesia\w*", "tr": r"turquia|turkey|turkish", "it": r"italia\w*|italy|italian\w*",
    "gr": r"greece|greek|griego\w*", "ir": r"iran\w*", "af": r"afganistan|afghan\w*", "pk": r"pakistan\w*",
    "nz": r"nueva zelanda|new zealand", "au": r"australia\w*", "tw": r"taiwan\w*",
}
_COUNTRY_RX = [(k, re.compile(r"(?<![a-z])(" + v + r")(?![a-z])")) for k, v in _COUNTRIES.items()]
_MAG_RX = re.compile(r"(?<![a-z])(?:magnitud|magnitude|m)\s*(?:preliminar\s*(?:de\s*)?)?(?:de\s*)?(\d)[.,](\d)")


def places(text: str) -> set[str]:
    t = fold(text).lower()
    return {k for k, rx in _COUNTRY_RX if rx.search(t)}


def magnitude(title: str):
    t = fold(title).lower()
    if not re.search(r"temblor|sismo|terremoto|quake|tremor|magnitud", t):
        return None
    m = _MAG_RX.search(t)
    return (m.group(1) + "." + m.group(2)) if m else None


# Parte de ataques (misiles, bombardeos, muertos) frente a nota diplomática (conversaciones, enviado,
# acusaciones): el mismo día de una guerra no son la misma historia aunque compartan «Ucrania» y «Zelenski».
_ATTACK = re.compile(r"(missiles? rain|blitz|barrage|kills? \d|killed|kills\b|dead\b|muert|mueren|deja \d|bombard|"
                     r"(drone|missile|air) (attack|strike)s?|ataques? (masivo|con (misiles|drones))|shelling|struck|hit by)")
_DIPLO = re.compile(r"(talks|conversacion|negociac|envoy|enviad|witkoff|rubio|summit|cumbre|meets|se reune|reunion|"
                    r"accus|acusa|delay|retras|sanction|sancion|peace|paz|diplomat|norway|noruega|oslo)")


def event_kind(title: str):
    t = fold(title).lower()
    att, dip = bool(_ATTACK.search(t)), bool(_DIPLO.search(t))
    return "attack" if att and not dip else ("diplo" if dip and not att else None)


def event_clash(a, b) -> bool:
    """Mismo tipo de hecho en lugares distintos (país del titular) o sismos de magnitud distinta."""
    ka, kb = a.get("_kind"), b.get("_kind")
    if ka and kb and ka != kb:
        return True
    ma, mb = a.get("_mag"), b.get("_mag")
    if ma and mb and ma != mb:
        return True
    pa, pb = a.get("_pl"), b.get("_pl")
    if pa and pb and not (pa & pb) and not (pa & b.get("_pla", set())) and not (pb & a.get("_pla", set())):
        return True
    return False


def names_clash(a_names, a_all, b_names, b_all, idf, rare_cut):
    """Cada lado nombra algo poco común que el otro no menciona en ninguna parte y no comparten
    ningún nombre: son hechos distintos aunque el resto del titular se parezca
    (p. ej. «Salomon abre su primera tienda en Costa Rica» y «BICIAN abre su primera tienda en Costa Rica»)."""
    na = {w for w in a_names if idf.get(w, 0) >= rare_cut}
    nb = {w for w in b_names if idf.get(w, 0) >= rare_cut}
    if not na or not nb or (na & nb):
        return False
    return not (na & b_all) and not (nb & a_all)


def build_vectors(items):
    docs = []
    lower = lowercase_terms(items)
    for it in items:
        it["_pn"] = title_names(it["title"], lower)
        it["_pl"] = places(it["title"])
        it["_pla"] = places(it["title"] + " " + it.get("summary", ""))
        it["_mag"] = magnitude(it["title"])
        it["_kind"] = event_kind(it["title"])
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
        if ok and (event_clash(a, b) or names_clash(a["_pn"], a["_all"], b["_pn"], b["_all"], idf, rare_cut)):
            ok = False
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
        clash = 0
        for x in A:
            for y in B:
                tot += sim(x, y)
                a_, b_ = items[x], items[y]
                if event_clash(a_, b_) or names_clash(a_["_pn"], a_["_all"], b_["_pn"], b_["_all"], idf, rare_cut):
                    clash += 1
        if tot / (len(A) * len(B)) < AVG_MIN:
            continue
        # Dos tercios o más de los pares nombran cosas distintas (otra marca, otro país, otra magnitud,
        # ataque frente a diplomacia): son hechos distintos.
        if clash * 3 >= 2 * len(A) * len(B):
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


# url -> resumen RSS de cada nota mostrada (lo usa narrar.py; no va a noticias.json).
ARTICLE_TEXT = {}


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
        ARTICLE_TEXT[m["url"]] = m.get("summary") or ""
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


TOPIC_TABS = ("politica", "sucesos", "guerras", "finanzas")
TOPIC_PRIO = {"guerras": 6, "sucesos": 5, "ciencias": 4, "finanzas": 3, "politica": 2, "mundo": 1}


def merge_pass(groups, pool, idf, hours=48):
    """Segunda pasada (tema.merge_split) solo sobre grupos de 2+ medios: une la misma noticia
    contada con otras palabras o en otro idioma. Las notas sueltas no se tocan (y así es rápido)."""
    import tema
    multi = [g for g in groups if len({pool[i]["org"] for i in g}) >= 2]
    rest = [g for g in groups if len({pool[i]["org"] for i in g}) < 2]
    # Con nombre propio en común se pide un centro algo más parecido (0.32) que en las pestañas temáticas:
    # aquí se mezclan todos los temas y, p. ej., «Zelenski critica a Trump» no debe unirse al ataque con drones.
    multi, merges = tema.merge_split(multi, pool, idf, len(pool), hours, anchor_cos=0.32, cos_strong=0.55,
                                    anchor_weak=0.38, cos_many_override=0.41)
    return multi + rest, merges


def story_topic(members):
    """Tema de una historia regional por votos de sus notas (como en el agrupador general).
    Solo cuenta si el tema tiene un respaldo claro; Finanzas pide mayoría."""
    votes = Counter(m.get("category") or "mundo" for m in members)
    n = len(members)
    if votes.get("guerras", 0) * 3 >= n:
        return "guerras"
    cat = max(votes, key=lambda c: (votes[c], TOPIC_PRIO.get(c, 0)))
    if cat not in TOPIC_TABS:
        return None
    if cat == "finanzas":
        return cat if votes[cat] * 2 >= n else None
    return cat if votes[cat] >= max(2, n * 0.34) else None


def _overlapping(tab, urls):
    """Tarjetas de `tab` que son (al menos a medias) la misma historia: la mitad o más de sus notas
    están en la historia. Compartir una sola nota no basta (otra historia relacionada no se borra)."""
    out = []
    for i, x in enumerate(tab):
        su = {y["url"] for y in x["sources"]}
        k = len(urls & su)
        if k and k * 2 >= len(su):
            out.append(i)
    return out


def _absorb(tab, idx, story):
    """Pone `story` en el lugar de la primera tarjeta de `idx` y quita las demás (eran parte de ella)."""
    tab[idx[0]] = story
    for i in sorted(idx[1:], reverse=True):
        del tab[i]


def add_regional_topics(out_cats, reg_cats, region_labels):
    """Historias regionales de 3+ medios con tema (Política, Sucesos, Guerras, Finanzas): si la pestaña temática
    ya tiene la misma historia con menos medios, la versión regional la reemplaza (después final_dedup deja una
    sola tarjeta). Ya no se agregan copias: el tema queda en «topic» y se cuenta en el informe."""
    by_id = {c["id"]: c for c in out_cats}
    added = Counter()
    for rc in reg_cats:
        for st in rc["stories"]:
            tid = st.get("topic")
            urls = {x["url"] for x in st["sources"]}
            copy = json.loads(json.dumps(st))
            copy.pop("topic", None)
            copy.pop("region", None)
            copy["chips"] = [{"id": rc["id"], "label": region_labels.get(rc["id"], rc["label"])}]
            # La misma historia ya en otra pestaña temática con menos medios: se cambia por la versión
            # regional (más completa) aunque su tema por votos sea otro.
            for oid in TOPIC_TABS:
                if oid == tid or oid not in by_id:
                    continue
                otab = by_id[oid]["stories"]
                od = _overlapping(otab, urls)
                if od and copy["outlets"] > max(otab[i]["outlets"] for i in od):
                    _absorb(otab, od, json.loads(json.dumps(copy)))
            if tid not in by_id:
                continue
            tab = by_id[tid]["stories"]
            dups = _overlapping(tab, urls)
            if dups:
                # Puede haber varias tarjetas parciales de la misma historia: la versión regional las absorbe.
                if copy["outlets"] > max(tab[i]["outlets"] for i in dups):
                    _absorb(tab, dups, copy)
                continue
            # Arreglo 1: ya no se copia. La historia regional queda marcada con «topic» y final_dedup()
            # decide su pestaña principal (PRIMARY_PRIO); la otra aparición va como chip «También en».
            added[tid] += 1
    for tid in TOPIC_TABS:
        if tid in by_id:
            lst = sorted(by_id[tid]["stories"], key=lambda s: (s["outlets"], s.get("lastSeen", "")), reverse=True)[:MAX_STORIES]
            for i, s in enumerate(lst):
                s["id"] = f"{tid}-{i + 1}"
            by_id[tid]["stories"] = lst
    return dict(added)


FRESH_HOURS = 24           # sin notas nuevas en 24 h -> sección "Anteriores"


def load_previous():
    """El noticias.json publicado (en GitHub Actions es el del checkout, antes de sobrescribirlo)."""
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return None


def apply_freshness(cats, prev, now):
    """Marca cada historia como Nuevo/Sigue comparando con la publicación anterior (misma pestaña,
    al menos una nota en común), ordena por actividad reciente y separa las que no tienen notas nuevas en 24 h."""
    # Se compara contra TODAS las pestañas de la publicación anterior: con la pestaña principal (Arreglo 1) una
    # historia puede cambiar de pestaña y no debe salir como «Nuevo». También cuentan los enlaces de Google ya
    # resueltos (gnUrl) y «En desarrollo» (si se confirma, sube con «Confirmada ✓»).
    prev_all, prev_dev = [], []
    if prev:
        for c in prev.get("categories", []):
            for s in c.get("stories", []):
                urls = {x["url"] for x in s.get("sources", [])} | {x["gnUrl"] for x in s.get("sources", []) if x.get("gnUrl")}
                (prev_dev if c["id"] == "posibles" else prev_all).append((urls, s.get("firstShown") or prev.get("updatedAt")))
    report = {}
    for c in cats:
        prev_tab = prev_all if c["id"] != "posibles" else prev_all + prev_dev
        for s in c["stories"]:
            urls = {x["url"] for x in s.get("sources", [])}
            hit = next((fs for u, fs in prev_tab if u & urls), None)
            last = max((x["publishedAt"] for x in s.get("sources", []) if x.get("publishedAt")), default=s.get("lastSeen"))
            s["lastArticle"] = last
            urls |= {x["gnUrl"] for x in s.get("sources", []) if x.get("gnUrl")}
            hit = next((fs for u, fs in prev_tab if u & urls), None)
            if prev is None:
                s["fresh"] = None
            elif hit:
                s["fresh"], s["firstShown"] = "sigue", hit
            else:
                s["fresh"], s["firstShown"] = "nuevo", iso(now.timestamp())
                if c["id"] != "posibles" and next((1 for u, _ in prev_dev if u & urls), None):
                    s["confirmed"] = True     # estaba «En desarrollo» y llegó a 3+ medios
            age_h = max(0.0, (now - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() / 3600) if last else 999
            s["stale"] = age_h > FRESH_HOURS
            # Actividad: la nota más reciente pesa más; los medios suman con logaritmo.
            s["_score"] = (1 + math.log(max(1, s.get("outlets", 1)))) * math.exp(-age_h / 12)
        c["stories"].sort(key=lambda s: (s["stale"], -s["_score"]))
        for s in c["stories"]:
            s.pop("_score", None)
        report[c["id"]] = {"total": len(c["stories"]), "nuevo": sum(1 for s in c["stories"] if s["fresh"] == "nuevo"),
                           "sigue": sum(1 for s in c["stories"] if s["fresh"] == "sigue"),
                           "anteriores": sum(1 for s in c["stories"] if s["stale"])}
    return report


POSIBLES_MAX = 60          # tope total de la pestaña "Posibles noticias"
POSIBLES_PER_CHIP = 8      # tope por categoría/región
POSIBLES_MIN_PER_CHIP = 3  # se reservan hasta 3 por categoría/región para que no las tapen otras
POSIBLES_MIN_CHIP = {"cripto": 6}  # Criptomonedas tiene 6 lugares asegurados


def build_posibles(candidates, out_cats, region_labels):
    """Grupos con 2 medios distintos que no están en ninguna pestaña de consenso (3+).
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


# Orden de pestañas pedido: Buenas, Costa Rica, Finanzas, Cripto, Política, Ciencias, Mundo (con las
# regiones dentro), Sucesos, Guerras y conflictos y Posibles noticias.
TAB_FIRST = ["buenas", "costarica", "finanzas", "cripto", "deportes", "politica", "ciencias", "mundo", "sucesos", "guerras", "posibles"]
CAT_TITLES = {"guerras": "Guerras y conflictos mundiales actuales"}

# Regiones que van dentro de la pestaña Mundo (Costa Rica sigue con pestaña propia).
MUNDO_REGIONS = ["centroamerica", "latam", "sudamerica", "europa", "asia", "africa", "oceania"]
MUNDO_SHORT = {"oceania": "Oceanía"}


def merge_mundo(cats):
    """Une la pestaña Mundo (general) con las regionales en una sola, con filtros por región.
    Una historia que está en Mundo general y en una región (comparten notas) queda en una
    sola tarjeta con sus etiquetas de región; se queda la versión con más medios."""
    by_id = {c["id"]: c for c in cats}
    general = by_id.get("mundo")
    if not general:
        return cats
    regs = [by_id[r] for r in MUNDO_REGIONS if r in by_id]
    merged = []
    for s in general["stories"]:
        merged.append({"s": s, "general": True, "regions": [], "urls": {x["url"] for x in s["sources"]}})
    for rc in regs:
        for s in rc["stories"]:
            urls = {x["url"] for x in s["sources"]}
            dup = next((m for m in merged if m["urls"] & urls), None)
            if dup:
                if rc["id"] not in dup["regions"]:
                    dup["regions"].append(rc["id"])
                if s["outlets"] > dup["s"]["outlets"]:
                    dup["s"] = s
                dup["urls"] |= urls
                continue
            merged.append({"s": s, "general": False, "regions": [rc["id"]], "urls": urls})
    labels = {rc["id"]: MUNDO_SHORT.get(rc["id"], rc["label"]) for rc in regs}
    out = []
    for m in sorted(merged, key=lambda m: (m["s"]["outlets"], m["s"]["lastSeen"]), reverse=True):
        s = dict(m["s"])
        s.pop("region", None)
        s["mundoGeneral"] = m["general"]
        s["mundoRegions"] = m["regions"]
        s["chips"] = [{"id": r, "label": labels[r]} for r in m["regions"]]
        out.append(s)
    for i, s in enumerate(out):
        s["id"] = f"mundo-{i + 1}"
    filters = [{"id": "general", "label": "General", "count": sum(1 for s in out if s["mundoGeneral"])}]
    filters += [{"id": r, "label": labels[r], "count": sum(1 for s in out if r in s["mundoRegions"])}
                for r in MUNDO_REGIONS if r in labels]
    general.update({"stories": out, "filters": filters})
    gone = {rc["id"] for rc in regs}
    return [c for c in cats if c["id"] not in gone]


def order_tabs(cats):
    cats = merge_mundo(cats)
    for c in cats:
        if c["id"] in CAT_TITLES:
            c["title"] = CAT_TITLES[c["id"]]
    first = [c for t in TAB_FIRST for c in cats if c["id"] == t]
    return first + [c for c in cats if c["id"] not in TAB_FIRST]


# ---------------------------------------------------------------- enlaces y deduplicado final (Arreglos 1 y 2)

def resolve_story_links(cats) -> dict:
    """Cambia los enlaces de Google Noticias de las fuentes por el enlace real del medio (enlaces.py).
    Prioridad del tope de decodificación: tarjetas de una sola fuente (Buenas) y la primera fuente de cada tarjeta."""
    first, rest = [], []
    for c in cats:
        for s in c.get("stories", []):
            for i, x in enumerate(s.get("sources", [])):
                if enlaces.is_gn(x.get("url", "")):
                    (first if i == 0 or len(s["sources"]) == 1 else rest).append((x["url"], x.get("title", "")))
    enlaces.resolve_many(first + rest)
    changed = still = 0
    for c in cats:
        for s in c.get("stories", []):
            out, keys = [], set()
            for x in s.get("sources", []):
                u = x.get("url", "")
                if enlaces.is_gn(u):
                    real = enlaces.CACHE.get(u)
                    if real and is_safe_http_url(clean_url(real)):
                        x["gnUrl"], x["url"] = u, clean_url(real)
                        x.pop("gn", None)
                        changed += 1
                    else:
                        x["gn"] = True
                        still += 1
                k = _url_key(x["url"])
                if k in keys:      # la misma nota llegó por Google y por el feed directo
                    continue
                keys.add(k)
                out.append(x)
            # El enlace principal de la tarjeta nunca es de Google si hay otro.
            out.sort(key=lambda x: bool(x.get("gn")))
            s["sources"] = out
    rep = enlaces.report()
    rep.update({"sourcesResolved": changed, "sourcesStillGoogle": still})
    return rep


def _url_key(u: str) -> str:
    p = urlparse(u)
    return (p.netloc.replace("www.", "") + p.path.rstrip("/")).lower()


# Prioridad editorial para la pestaña principal de una historia repetida (plan, Arreglo 1; decisión del
# creador del 2026-11-17: una buena noticia tica va primero en Costa Rica, con chip «También en Avances»).
PRIMARY_PRIO = ["guerras", "sucesos", "costarica", "buenas", "finanzas", "cripto", "ciencias", "politica", "mundo"]
DEDUP_TABS = set(PRIMARY_PRIO)
TITLE_SAME = 0.85        # titulares casi iguales (Jaccard sobre terms(), une ES/EN por el vocabulario común)
TITLE_SAME_NAMED = 0.6   # parecidos y con el mismo nombre propio raro, dentro de PAIR_WINDOW_H
SECTION_OF = {"costarica": "costarica", "guerras": "mundo", "sucesos": "mundo", "politica": "mundo", "mundo": "mundo",
              "finanzas": "dinero", "cripto": "dinero", "buenas": "avances", "ciencias": "avances", "deportes": "deportes"}
SECTION_LABELS = {"hoy": "Hoy", "costarica": "Costa Rica", "mundo": "Mundo", "dinero": "Dinero", "deportes": "Deportes",
                  "avances": "Avances"}
FACET_OF = {"guerras": "conflictos", "sucesos": "sucesos", "politica": "politica", "finanzas": "finanzas",
            "cripto": "cripto", "ciencias": "ciencias", "buenas": "buenas"}


def _story_terms(s) -> set:
    out = set()
    for h in {s.get("headline"), s.get("headlineEs"), s.get("headlineEn")} - {None, ""}:
        out |= set(terms(GN_TITLE_SUFFIX.sub("", h)))
    return out


def _story_names(s) -> set:
    out = set()
    for h in {s.get("headline"), s.get("headlineEs"), s.get("headlineEn")} - {None, ""}:
        out |= {w.lower() for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}\b", h)}
    return out - _NOT_NAMES_DEDUP


_NOT_NAMES_DEDUP = {"este", "esta", "tras", "para", "como", "with", "after", "says", "from", "that", "this", "what", "when",
                    "costa", "rica", "estados", "unidos", "united", "states", "trump", "gobierno", "government"}


def _ts_of(s):
    v = s.get("lastSeen") or s.get("firstSeen")
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def same_story(a, b) -> str | None:
    """Motivo si dos tarjetas son la misma historia: 2+ notas en común (o la mitad de la menor) o titular parecido."""
    ua, ub = a["_keys"], b["_keys"]
    shared = len(ua & ub)
    if shared >= 2 or (shared and shared * 2 >= min(len(ua), len(ub))):
        return f"enlaces ({shared})"
    ta, tb = a["_terms"], b["_terms"]
    if len(ta) < 4 or len(tb) < 4:
        return None
    j = len(ta & tb) / len(ta | tb)
    if j >= TITLE_SAME:
        return f"titular {j:.2f}"
    if j >= TITLE_SAME_NAMED and a["_names"] & b["_names"]:
        x, y = _ts_of(a["s"]), _ts_of(b["s"])
        if x and y and abs(x - y) <= PAIR_WINDOW_H * 3600:
            ka, kb = event_kind(a["s"].get("headline", "")), event_kind(b["s"].get("headline", ""))
            ma, mb = magnitude(a["s"].get("headline", "")), magnitude(b["s"].get("headline", ""))
            if not (ka and kb and ka != kb) and not (ma and mb and ma != mb):
                return f"titular {j:.2f} + nombre"
    return None


def _cand_cats(cid, s):
    """Pestañas posibles de una tarjeta: donde está, su tema regional y Costa Rica si es una buena noticia tica."""
    out = [cid]
    if s.get("topic") in DEDUP_TABS and s["topic"] not in out:
        out.append(s["topic"])
    if cid == "buenas" and s.get("cr"):
        out.append("costarica")
    return out


def final_dedup(cats):
    """Una tarjeta por historia (Arreglos 1 y 2). Une copias entre pestañas y dentro de la misma (enlaces o titular
    parecido, también ES/EN), elige la pestaña principal por PRIMARY_PRIO y guarda las demás en «alsoIn».
    Quita de «posibles» lo que ya está confirmado. Devuelve la lista de categorías (mismo orden)."""
    labels = {c["id"]: c.get("label", c["id"]) for c in cats}
    cards = []
    for c in cats:
        if c["id"] not in DEDUP_TABS:
            continue
        for s in c["stories"]:
            cards.append({"cid": c["id"], "s": s, "_keys": {_url_key(x["url"]) for x in s.get("sources", [])},
                          "_terms": _story_terms(s), "_names": _story_names(s)})
    n = len(cards)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    merges = []
    by_key = defaultdict(list)
    for i, cd in enumerate(cards):
        for k in cd["_keys"]:
            by_key[k].append(i)
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            why = same_story(cards[i], cards[j])
            if why:
                parent[find(j)] = find(i)
                merges.append({"a": f'{cards[i]["cid"]}: {cards[i]["s"].get("headline", "")[:90]}',
                               "b": f'{cards[j]["cid"]}: {cards[j]["s"].get("headline", "")[:90]}', "why": why})
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(cards[i])
    rank = {c: i for i, c in enumerate(PRIMARY_PRIO)}
    placed = defaultdict(list)
    for g in groups.values():
        cand = []
        for cd in g:
            for c in _cand_cats(cd["cid"], cd["s"]):
                if c not in cand:
                    cand.append(c)
        present = [c for c in cand if c in labels] or cand
        primary = min(present, key=lambda c: rank.get(c, 99))
        base_cd = max(g, key=lambda cd: (cd["s"].get("outlets", 0), bool(cd["s"].get("narrKind")), cd["cid"] == primary))
        st = base_cd["s"]
        names = set(st.get("outletNames") or [])
        have = {_url_key(x["url"]) for x in st.get("sources", [])}
        for cd in g:
            o = cd["s"]
            if o is st:
                continue
            for x in o.get("sources", []):
                k = _url_key(x["url"])
                if k not in have:
                    have.add(k)
                    st["sources"].append(x)
                    if x.get("source") and x["source"] not in names:
                        names.add(x["source"])
                        st["outlets"] = st.get("outlets", 0) + 1
            for key in ("subtopic", "subtopicLabel", "cr", "region", "topic", "alsoOnReddit"):
                if o.get(key) and not st.get(key):
                    st[key] = o[key]
            if o.get("mundoRegions"):
                st["mundoRegions"] = sorted(set(st.get("mundoRegions") or []) | set(o["mundoRegions"]))
                st["mundoGeneral"] = bool(st.get("mundoGeneral") or o.get("mundoGeneral"))
                old = {ch["id"] for ch in st.get("chips") or []}
                st["chips"] = (st.get("chips") or []) + [ch for ch in o.get("chips") or [] if ch["id"] not in old]
        if names and st.get("outletNames") is not None:
            st["outletNames"] = sorted(names)
        st["sources"].sort(key=lambda x: bool(x.get("gn")))
        cats_in = []
        for cd in g:
            if cd["cid"] not in cats_in:
                cats_in.append(cd["cid"])
        for c in cand:
            if c not in cats_in:
                cats_in.append(c)
        st["_cats"] = cats_in
        st["alsoIn"] = [{"id": c, "label": labels.get(c, c)} for c in cats_in if c != primary]
        if not st["alsoIn"]:
            st.pop("alsoIn")
        placed[primary].append(st)
    confirmed_keys = set()
    for lst in placed.values():
        for st in lst:
            confirmed_keys |= {_url_key(x["url"]) for x in st.get("sources", [])}
    dropped_pos = 0
    for c in cats:
        if c["id"] in DEDUP_TABS:
            lst = placed.get(c["id"], [])
            lst.sort(key=lambda s: (s.get("outlets", 0), s.get("lastSeen", "")), reverse=True)
            for i, st in enumerate(lst):
                st["id"] = f'{c["id"]}-{i + 1}'
            c["stories"] = lst
        elif c["id"] == "posibles":
            keep = [s for s in c["stories"] if not ({_url_key(x["url"]) for x in s.get("sources", [])} & confirmed_keys)]
            dropped_pos = len(c["stories"]) - len(keep)
            c["stories"] = keep
    # Pestañas nuevas que solo existen como principal (p. ej. Costa Rica sin historias propias)
    report = {"cardsBefore": n, "storiesAfter": len(groups), "merged": n - len(groups),
              "posiblesAlreadyConfirmed": dropped_pos, "merges": merges[:200]}
    return cats, report


# Frentes de Conflictos (estructura §6): presentación agrupada, nunca para ocultar.
CONFLICTS = [
    ("ucrania-rusia", "Ucrania–Rusia", re.compile(r"(?<![a-z])(ucrani\w*|ukrain\w*|rusia|russia\w*|kiev|kyiv|crimea|kremlin|donbas|zelensk\w*|putin)(?![a-z])")),
    ("medio-oriente", "Medio Oriente", re.compile(r"(?<![a-z])(israel\w*|gaza|iran\w*|irani|libano|lebanon|hezbol\w*|hamas|yemen\w*|huti\w*|houthi\w*|siria|syria\w*|cisjordania|west bank|palestin\w*)(?![a-z])")),
    ("sudan", "Sudán", re.compile(r"(?<![a-z])(sudan\w*|darfur|el fasher|rsf)(?![a-z])")),
    ("sahel-africa", "Sahel y África", re.compile(r"(?<![a-z])(sahel|mali|burkina|niger\b|somalia|al.shabaab|congo|m23|etiopia|ethiopia|tigray)(?![a-z])")),
    ("asia", "Asia", re.compile(r"(?<![a-z])(myanmar|birmania|taiwan|corea del norte|north korea|cachemira|kashmir|pakistan|afganistan|afghanistan)(?![a-z])")),
    ("americas", "Américas", re.compile(r"(?<![a-z])(haiti|venezuel\w*|colombia\w*|ecuador\w*|carteles?|cartel)(?![a-z])")),
]


def conflict_front(s):
    t = fold(" ".join(filter(None, [s.get("headline"), s.get("headlineEs"), s.get("headlineEn")]))).lower()
    for cid, label, rx in CONFLICTS:
        if rx.search(t):
            return {"id": cid, "label": label}
    return {"id": "otros", "label": "Otros frentes"}


HEAVY_TONE = re.compile(r"(?<![a-z])(muert\w*|mueren|murio|asesin\w*|homicid\w*|ataque\w*|bombarde\w*|dead|killed|kills?|"
                        r"attack\w*|strike\w*|suicid\w*|violaci\w*|secuestr\w*|masacre|tiroteo|shooting|war|guerra)(?![a-z])")


def story_tone(s, facets) -> str:
    """Solo para el ORDEN de Hoy (alternar ritmo); nunca para ocultar, plegar ni poner topes."""
    if "conflictos" in facets or "sucesos" in facets:
        return "heavy"
    t = fold(s.get("headline", "")).lower()
    if HEAVY_TONE.search(t):
        return "heavy"
    if "buenas" in facets or "ciencias" in facets:
        return "light"
    return "neutral"


def _cr_story(s) -> bool:
    try:
        import regiones
    except Exception:
        return False
    t = fold(" ".join(filter(None, [s.get("headline"), s.get("headlineEs")]))).lower()
    return bool(regiones.KW["costarica"].search(t))


def assign_sections(cats) -> dict:
    """Campos de la estructura de 6 secciones en cada historia: section, facets, alsoIn con sección, tone y
    conflict. Las categorías viejas (ids) no cambian, así la app Android y las pruebas no se rompen."""
    per = Counter()
    for c in cats:
        cid = c["id"]
        if cid not in DEDUP_TABS and cid != "deportes":
            continue
        for st in c["stories"]:
            cats_in = st.pop("_cats", None) or [cid] + ([st["topic"]] if st.get("topic") in DEDUP_TABS else [])
            facets = []
            for x in cats_in:
                f = FACET_OF.get(x)
                if f and f not in facets:
                    facets.append(f)
            is_cr = ("costarica" in cats_in or bool(st.get("cr")) or st.get("region") == "costarica"
                     or (cid in ("politica", "sucesos") and _cr_story(st)))
            sec = "costarica" if is_cr and cid != "guerras" else SECTION_OF.get(cid, "mundo")
            st["section"] = sec
            st["facets"] = facets
            also = []
            for a in st.get("alsoIn", []):
                a_sec = SECTION_OF.get(a["id"], "mundo")
                if a["id"] in ("politica", "sucesos") or a_sec == sec:
                    a_sec = sec
                a.update({"section": a_sec, "sectionLabel": SECTION_LABELS[a_sec]})
                if a_sec == sec:
                    a["sameSection"] = True
                also.append(a)
            if sec == "costarica" and "buenas" in facets and not any(a["section"] == "avances" for a in also):
                also.append({"id": "buenas", "label": "Buenas noticias", "section": "avances", "sectionLabel": "Avances"})
            if also:
                st["alsoIn"] = also
            st["tone"] = story_tone(st, facets)
            if "conflictos" in facets:
                st["conflict"] = conflict_front(st)
            per[sec] += 1
    return dict(per)


def main():
    now = datetime.now(timezone.utc)
    previous = load_previous()   # leer antes de sobrescribir noticias.json
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
        raw_newest = max((d for d in (parse_date(r[2]) for r in rows) if d), default=None)
        gnews = "news.google.com" in url
        for title, link, date_s, desc in rows:
            if gnews:  # Google Noticias agrega « - Medio» al titular y el resumen es solo el titular
                title, desc = GN_TITLE_SUFFIX.sub("", title).strip(), ""
            if len(title) < 18 or SKIP_TITLE.search(title) or SECTION_TITLE.search(title):
                continue
            url_c = clean_url(link)
            if not is_safe_http_url(url_c):
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
        frozen = frozen_reason(fid, raw_newest, now)
        if frozen:  # responde pero no aporta: se hace visible en feedsFailed en vez de quedarse callado
            ok_feeds[-1]["frozen"] = True
            failed.append({"id": fid, "source": source, "url": url, "error": frozen})
            print(f"FROZEN {fid}: {frozen}")
        print(f"OK   {fid:22s} raw={len(rows):3d} kept={kept}")

    for fid, url, reason in KNOWN_FAILS:
        failed.append({"id": fid, "source": fid, "url": url, "error": reason, "known": True})

    print(f"\nitems={len(pool)}")
    idf, df = build_vectors(pool)
    groups, sims = cluster(pool, idf, df)
    groups, main_merges = merge_pass(groups, pool, idf)

    stories_by_cat = defaultdict(list)
    candidates = []          # grupos de 2 medios: van a "Posibles noticias"
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

    # Refuerzo de Finanzas y Ciencias con medios especializados (ver tema.py); misma regla de 3+.
    topic_reports = {}
    for tcat in ("finanzas", "ciencias"):
        try:
            import tema
            before = (len(stories_by_cat.get(tcat, [])), sum(1 for c in candidates if c.get("category") == tcat))
            t_st, t_cand, t_rep, t_dbg, t_merges = tema.build(tcat, now, pool, {f[1] for f in FEEDS})
            stories_by_cat[tcat] = t_st
            candidates = [c for c in candidates if c.get("category") != tcat] + t_cand
            t_rep["before"] = {"stories": before[0], "candidates": before[1]}
            topic_reports[tcat] = t_rep
            print(tcat, "antes", before, "después", (len(t_st), len(t_cand)), t_rep["groupsByOutletCount"])
        except Exception as exc:  # nunca romper la actualización principal
            topic_reports[tcat] = {"error": f"{type(exc).__name__}: {exc}"}
            print(tcat, "FAIL", type(exc).__name__, exc)

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
            # Pestaña "Criptomonedas": solo historias con 3+ medios distintos (ver cripto.py).
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

    # Pestañas regionales: 3+ medios distintos, región por lugares nombrados (ver regiones.py).
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
        region_report["topicAdds"] = add_regional_topics(out_cats, reg_cats, dict(MUNDO_SHORT, **{k: v for k, v in regiones.REGIONS if k not in MUNDO_SHORT}))
        for tid in TOPIC_TABS:
            summary_counts[tid] = len(next((c["stories"] for c in out_cats if c["id"] == tid), []))
        print("temas desde regiones", region_report["topicAdds"])
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

    # Pestaña "Posibles noticias": grupos de 2 medios distintos que NO llegaron a 3.
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
        if buenas.A.ARTICLE_TEXT is not ARTICLE_TEXT:  # al correr como script, buenas importa otra copia del módulo
            ARTICLE_TEXT.update(buenas.A.ARTICLE_TEXT)
        out_cats.append({"id": "buenas", "label": "Buenas noticias", "minOutlets": 1, "stories": good})
        summary_counts["buenas"] = len(good)
        print("buenas", good_report["perSubtopic"], "leads", good_report["leads"]["confirmed"], "/", good_report["leads"]["total"])
    except Exception as exc:  # nunca romper la actualización principal
        print("buenas FAIL", type(exc).__name__, exc)

    exchange, exchange_report = None, None
    try:  # tipo de cambio para el encabezado; nunca rompe la actualización
        import tipocambio
        exchange, exchange_report = tipocambio.build(now)
        print("tipo de cambio", exchange_report)
    except Exception as exc:
        print("tipo de cambio FAIL", type(exc).__name__, exc)

    crypto_prices, crypto_prices_report = None, None
    try:  # precios y gráficas de cripto para la pestaña Criptomonedas; nunca rompe la actualización
        import criptoprecios
        crypto_prices, crypto_prices_report = criptoprecios.build(now)
        print("precios cripto", crypto_prices_report)
    except Exception as exc:
        print("precios cripto FAIL", type(exc).__name__, exc)

    sports, sports_report = None, None
    try:  # marcadores de NFL, CFB, NBA, CBB, MLB, NHL, tenis y MMA (ESPN); nunca rompe la actualización
        import resultados
        sports, sports_report = resultados.build(now)
        print("resultados deportivos", sports_report)
    except Exception as exc:
        print("resultados deportivos FAIL", type(exc).__name__, exc)
    # Pestaña de marcadores, no de noticias: sin historias; la app la llena con «sports».
    out_cats.append({"id": "deportes", "label": "Deportes", "kind": "scores", "minOutlets": 0, "stories": []})

    final_cats = order_tabs(out_cats)
    links_report = dedup_report = None
    section_counts = {}
    try:  # Arreglos 1 y 2: enlaces reales en vez de Google Noticias, una tarjeta por historia, secciones
        enlaces.seed_from_previous(previous)
        links_report = resolve_story_links(final_cats)
        print("enlaces Google Noticias", links_report)
        final_cats, dedup_report = final_dedup(final_cats)
        section_counts = assign_sections(final_cats)
        print("deduplicado final", {k: v for k, v in dedup_report.items() if k != "merges"}, "secciones", section_counts)
    except Exception as exc:  # nunca romper la actualización principal
        import traceback
        traceback.print_exc()
        dedup_report = {"error": f"{type(exc).__name__}: {exc}"}
    fresh_report = apply_freshness(final_cats, previous, now)
    print("frescura", fresh_report)
    narr_report = None
    try:  # relato con IA de todas las fuentes; sin clave o si falla, queda el resumen de un medio
        import narrar
        narr_report = narrar.narrate(final_cats, ARTICLE_TEXT, now)
        print("narración IA", narr_report)
    except Exception as exc:  # nunca romper la actualización principal
        print("narración IA FAIL", type(exc).__name__)
    payload = {
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exchange": exchange,
        "exchangeReport": exchange_report,
        "cryptoPrices": crypto_prices,
        "cryptoPricesReport": crypto_prices_report,
        "sports": sports,
        "sportsReport": sports_report,
        "nextRefreshAt": next_cron(now).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "refreshHours": REFRESH_HOURS,
        "method": {
            "minOutlets": MIN_OUTLETS,
            "pairWindowHours": PAIR_WINDOW_H,
            "newsMaxAgeHours": NEWS_HOURS,
            "description": "Agrupación por TF-IDF y términos distintivos comunes (ES/EN), solo grupos con 3+ medios distintos.",
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
        "categories": final_cats,
        "freshness": fresh_report,
        "feedsOk": ok_feeds,
        "feedsFailed": failed,
        "goodNews": good_report,
        "crypto": crypto_report,
        "topics": topic_reports,
        "regions": region_report,
        "mainMerges": [{"a": a, "b": b, "cos": c, "anchor": an, "shared": sh} for a, b, c, an, sh in main_merges],
        "possible": posibles_report,
        "links": links_report,
        "dedup": dedup_report,
        "sectionCounts": section_counts,
        "narration": narr_report,
    }
    write_json_atomic(OUT, payload)
    print("clusters", len(groups), "consensus", summary_counts)

    if DEBUG:
        with open(ROOT / "debug_clusters.txt", "w", encoding="utf-8") as fh:
            for cat, k, members in sorted(debug_rows, key=lambda r: (-r[1], r[0])):
                fh.write(f"\n=== [{cat}] {k} medios\n")
                for m in sorted(members, key=lambda m: m["org"]):
                    fh.write(f"  {m['lang']} {m['source'][:18]:18s} {m['title'][:110]}\n")


def validate_payload(payload) -> None:
    """Esquema mínimo de noticias.json; si falla, no se escribe (ni se publica)."""
    if not isinstance(payload, dict):
        raise ValueError("payload no es objeto")
    if not isinstance(payload.get("updatedAt"), str):
        raise ValueError("updatedAt falta")
    cats = payload.get("categories")
    if not isinstance(cats, list) or not cats:
        raise ValueError("categories vacío")
    for c in cats:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not isinstance(c.get("stories"), list):
            raise ValueError("categoría inválida")
        for st in c["stories"]:
            for src in st.get("sources", []):
                if not is_safe_http_url(src.get("url", "")):
                    raise ValueError("url de fuente inválida")


def write_json_atomic(path: Path, payload) -> None:
    validate_payload(payload)
    text = json.dumps(payload, ensure_ascii=False, indent=1, allow_nan=False)
    json.loads(text)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


if __name__ == "__main__":
    main()
