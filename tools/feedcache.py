"""Grabación y reproducción de las descargas (solo para pruebas locales; nunca en GitHub Actions).

Se activa con NOTICIAS_FEED_CACHE=/ruta/carpeta y NOTICIAS_FEED_MODE:
  record  -> descarga en vivo y guarda cada respuesta (o error) por URL
  replay  -> lee solo de la carpeta; si una URL no está grabada, falla como error de red
  replay+record (por defecto) -> lee de la carpeta y descarga en vivo solo lo que falte

Parchea urllib.request.urlopen y subprocess.run (solo las llamadas a curl), así sirve igual para el
código de main y el de la rama sin tocarlo. Las llamadas a APIs de IA (POST) nunca se graban.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

_LOCK = threading.Lock()
AI_HOSTS = ("x.ai", "openai.com", "groq.com", "googleapis.com", "anthropic.com")
_REAL_URLOPEN = urllib.request.urlopen
_REAL_RUN = subprocess.run
STATS = {"hit": 0, "miss": 0, "live": 0, "error": 0}


def _dir() -> Path:
    d = Path(os.environ["NOTICIAS_FEED_CACHE"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mode() -> str:
    return os.environ.get("NOTICIAS_FEED_MODE", "replay+record")


def _key(kind: str, url: str) -> str:
    return hashlib.sha1(f"{kind}|{url}".encode()).hexdigest()


def _load(kind, url):
    p = _dir() / (_key(kind, url) + ".json")
    if not p.exists():
        return None
    meta = json.loads(p.read_text())
    body = (_dir() / (_key(kind, url) + ".bin")).read_bytes() if meta.get("ok") else b""
    return meta, body


def _save(kind, url, ok, body=b"", status=None, error=None, final_url=None):
    with _LOCK:
        k = _key(kind, url)
        if ok:
            (_dir() / (k + ".bin")).write_bytes(body)
        (_dir() / (k + ".json")).write_text(json.dumps(
            {"kind": kind, "url": url, "ok": ok, "status": status, "error": error, "finalUrl": final_url}))


class _Resp(io.BytesIO):
    def __init__(self, body, url, status=200):
        super().__init__(body)
        self.status, self.url = status, url
        self.headers = {}

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def info(self):
        return self.headers


def urlopen(req, *a, **kw):
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    method = req.get_method() if isinstance(req, urllib.request.Request) else "GET"
    host = urlparse(url).hostname or ""
    if method != "GET" and (host.endswith(AI_HOSTS) or "news.google.com" not in host):
        return _REAL_URLOPEN(req, *a, **kw)        # IA u otras APIs: nunca se graban
    if method != "GET":                            # decodificador de Google Noticias (POST batchexecute)
        body = req.data or b""
        url = url + "#post=" + hashlib.sha1(body if isinstance(body, bytes) else str(body).encode()).hexdigest()
        kind = "urlopen:post"
    elif isinstance(req, urllib.request.Request):
        # Cabeceras distintas (simple=True) dan la misma URL; se distingue por Accept para no mezclar reintentos.
        kind = "urlopen:" + ("simple" if "Accept" not in req.headers and "Accept-encoding" not in req.headers else "full")
    else:
        kind = "urlopen:full"
    mode = _mode()
    if mode != "record":
        got = _load(kind, url)
        if got:
            STATS["hit"] += 1
            meta, body = got
            if meta["ok"]:
                return _Resp(body, meta.get("finalUrl") or url, meta.get("status") or 200)
            if meta.get("status"):
                raise urllib.error.HTTPError(url, meta["status"], meta.get("error") or "", {}, None)
            raise urllib.error.URLError(meta.get("error") or "error grabado")
        STATS["miss"] += 1
        if mode == "replay":
            raise urllib.error.URLError("no grabado (modo replay)")
    STATS["live"] += 1
    try:
        with _REAL_URLOPEN(req, *a, **kw) as r:
            body = r.read(30_000_000)
            status, final = getattr(r, "status", 200), r.geturl()
    except urllib.error.HTTPError as e:
        STATS["error"] += 1
        _save(kind, url, False, status=e.code, error=str(e.reason)[:200])
        raise
    except Exception as e:
        STATS["error"] += 1
        _save(kind, url, False, error=f"{type(e).__name__}: {str(e)[:200]}")
        raise
    _save(kind, url, True, body, status, final_url=final)
    return _Resp(body, final, status)


def run(args, *a, **kw):
    if not (isinstance(args, (list, tuple)) and args and args[0] == "curl"):
        return _REAL_RUN(args, *a, **kw)
    url = args[-1]
    kind = "curl"
    mode = _mode()
    if mode != "record":
        got = _load(kind, url)
        if got:
            STATS["hit"] += 1
            return subprocess.CompletedProcess(args, 0, got[1], b"")
        STATS["miss"] += 1
        if mode == "replay":
            return subprocess.CompletedProcess(args, 7, b"", b"no grabado")
    STATS["live"] += 1
    res = _REAL_RUN(args, *a, **kw)
    _save(kind, url, True, res.stdout or b"")
    return res


def install():
    if not os.environ.get("NOTICIAS_FEED_CACHE"):
        return False
    urllib.request.urlopen = urlopen
    subprocess.run = run
    return True
