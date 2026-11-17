"""Enlaces de Google Noticias -> enlace real del medio (Arreglo 2 del plan de mejoras de contenido).

Las búsquedas «site:» de Google Noticias (respaldos de regiones, tema, cripto y buenas ticas) traen enlaces
news.google.com/rss/articles/… en vez del enlace del medio. Así nadie reconoce que es la misma nota que ya
llegó por el feed directo (caso Quepos: Buenas con enlace de Google y Costa Rica con el de El Observador).

Orden para resolver, de más barato a más caro:
1. Caché (incluye lo ya resuelto en la publicación anterior: campo «gnUrl» de cada fuente).
2. Mismo titular en un feed directo leído en esta corrida (índice que llena actualizar.fetch_feed).
3. Decodificar el identificador con Google (2 peticiones), con tope por corrida, timeout corto y
   corte si Google empieza a fallar (p. ej. 429). Si no se puede, queda el enlace de Google y la fuente
   se marca gn: true.
Este módulo es único por proceso (actualizar.py corre como __main__ y los módulos lo importan como
«actualizar»; ambos comparten este índice y esta caché).
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
MAX_DECODES = 60        # decodificaciones con Google por corrida (2 peticiones cada una)
TIMEOUT = 8
FAIL_STREAK_STOP = 5    # tras 5 fallos seguidos se deja de pedir (Google limitando)
GN_SUFFIX = re.compile(r"\s+[-|–]\s+[^-|–]{2,45}$")

_LOCK = threading.Lock()
TITLE_INDEX: dict[str, str] = {}     # titular normalizado -> enlace directo
CACHE: dict[str, str | None] = {}    # enlace de Google -> enlace real (None = no se pudo)
STATS = {"cache": 0, "title": 0, "decoded": 0, "failed": 0, "skippedBudget": 0, "previous": 0}
_state = {"decodes": 0, "streak": 0}


def is_gn(url: str) -> bool:
    return "news.google.com/" in (url or "")


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "", t)[:90]


def index_items(rows) -> None:
    """rows: (título, enlace, fecha, resumen) de un feed directo (no Google)."""
    with _LOCK:
        for row in rows or ():
            title, link = row[0], row[1]
            if not link or is_gn(link) or not link.startswith("http"):
                continue
            k = norm_title(title)
            if len(k) >= 20:
                TITLE_INDEX.setdefault(k, link)


def seed_from_previous(prev) -> None:
    if not prev:
        return
    for c in prev.get("categories", []):
        for s in c.get("stories", []):
            for x in s.get("sources", []):
                if x.get("gnUrl") and x.get("url") and not is_gn(x["url"]):
                    CACHE.setdefault(x["gnUrl"], x["url"])
                    STATS["previous"] += 1


def _http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(2_000_000).decode("utf-8", "ignore")


def _gn_decode(url: str) -> str | None:
    """Decodifica un enlace news.google.com/rss/articles/<id> con el mismo pedido que hace la página de Google."""
    m = re.search(r"/(?:rss/)?articles/([^?/#]+)", url)
    if not m:
        return None
    aid = m.group(1)
    html = _http(f"https://news.google.com/articles/{aid}")
    sg = re.search(r'data-n-a-sg="([^"]+)"', html)
    ts = re.search(r'data-n-a-ts="([^"]+)"', html)
    if not (sg and ts):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                            "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts.group(1)), sg.group(1)]
    body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])}).encode()
    txt = _http("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    parts = txt.split("\n\n")
    if len(parts) < 2:
        return None
    arr = json.loads(parts[1])
    real = json.loads(arr[0][2])[1]
    return real if isinstance(real, str) and real.startswith("http") and not is_gn(real) else None


def resolve(url: str, title: str = "", allow_decode: bool = True) -> str | None:
    """Enlace real para un enlace de Google Noticias, o None si no se pudo."""
    if not is_gn(url):
        return url
    if url in CACHE:
        STATS["cache"] += 1
        return CACHE[url]
    k = norm_title(GN_SUFFIX.sub("", title or ""))
    if len(k) >= 20 and k in TITLE_INDEX:
        STATS["title"] += 1
        CACHE[url] = TITLE_INDEX[k]
        return CACHE[url]
    if not allow_decode:
        return None
    with _LOCK:
        if _state["decodes"] >= MAX_DECODES or _state["streak"] >= FAIL_STREAK_STOP:
            STATS["skippedBudget"] += 1
            return None
        _state["decodes"] += 1
    try:
        real = _gn_decode(url)
    except Exception:
        real = None
    with _LOCK:
        if real:
            _state["streak"] = 0
            STATS["decoded"] += 1
        else:
            _state["streak"] += 1
            STATS["failed"] += 1
        CACHE[url] = real
    return real


def resolve_many(items, workers: int = 4) -> None:
    """items: lista de (url, título) en orden de prioridad (las primeras gastan el tope primero)."""
    todo = [(u, t) for u, t in items if is_gn(u)]
    # Primero lo gratis (caché y titulares) para no gastar el tope en lo que ya se sabe.
    rest = []
    for u, t in todo:
        if resolve(u, t, allow_decode=False) is None and u not in CACHE:
            rest.append((u, t))
    seen, uniq = set(), []
    for u, t in rest:
        if u not in seen:
            seen.add(u)
            uniq.append((u, t))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda ut: resolve(*ut), uniq))


def report() -> dict:
    return dict(STATS, decodeBudget=MAX_DECODES, titleIndex=len(TITLE_INDEX))
