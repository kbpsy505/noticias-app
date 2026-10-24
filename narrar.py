"""Relato de cada historia a partir de TODAS sus fuentes.

Dos niveles, por historia:
1. IA (si hay clave): cualquier API compatible con OpenAI (/chat/completions): xAI (por
   defecto), Google Gemini, Groq, etc. Recibe titular, resumen RSS, medio y fecha de cada
   nota y escribe un relato neutral de 4-6 frases en español y en inglés usando SOLO esos
   textos. Caché en narraciones.json por el conjunto de notas; solo se vuelve a narrar
   cuando cambian. Tope de llamadas por corrida, en paralelo, con timeout y plazo total.
2. Extracto sin IA (siempre disponible): frases clave, sin repetir, de los resúmenes de
   varios medios, cada una atribuida («Según X, …»). Nada se reescribe.
Si nada de eso sirve, la tarjeta queda como antes (resumen de un medio).

Configuración (variables de entorno; vacías = no definidas):
  NARRA_API_KEY   clave (alias: XAI_API_KEY). Nunca se imprime ni se guarda.
  NARRA_API_URL   base del endpoint (por defecto https://api.x.ai/v1) o la URL completa
                  de /chat/completions. Ej.: https://generativelanguage.googleapis.com/v1beta/openai
                  o https://api.groq.com/openai/v1
  NARRA_MODEL     modelo (por defecto según el proveedor, ver DEFAULT_MODELS).
  NARRA_MAX_CALLS, NARRA_WORKERS, NARRA_RPM (límite de solicitudes por minuto, para planes
  gratis), NARRA_TIMEOUT, NARRA_DEADLINE, NARRA_PRICE_IN / NARRA_PRICE_OUT (US$/millón de
  tokens, solo para estimar costo), NARRAR=0 (apaga todo).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "narraciones.json"
CR = timezone(timedelta(hours=-6))


def _env(*names, default=""):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


API_URL = _env("NARRA_API_URL", "XAI_BASE_URL", default="https://api.x.ai/v1").rstrip("/")
if not API_URL.endswith("/chat/completions"):
    API_URL += "/chat/completions"
HOST = urlparse(API_URL).hostname or "?"
# Modelos por proveedor (oct 2026). NARRA_MODEL manda. En los planes gratis:
# Gemini Flash-Lite ~15 RPM / 500 RPD (Flash solo ~20 RPD); Groq qwen3.8-27b 30 RPM, 8K TPM, 2M TPD.
DEFAULT_MODELS = {
    "api.x.ai": "grok-4.20-0309-non-reasoning",
    "generativelanguage.googleapis.com": "gemini-3.5-flash-lite",
    "api.groq.com": "qwen/qwen3.8-27b",
}
MODEL = _env("NARRA_MODEL", "XAI_MODEL", default=DEFAULT_MODELS.get(HOST, "grok-4.20-0309-non-reasoning"))
# Modelos con razonamiento: pedir poco (más rápido y barato). xAI non-reasoning no lo necesita.
REASONING = _env("NARRA_REASONING", default="low" if HOST == "generativelanguage.googleapis.com"
                 or MODEL.startswith("openai/gpt-oss") else "")
MAX_CALLS = int(_env("NARRA_MAX_CALLS", default="150"))
WORKERS = int(_env("NARRA_WORKERS", default="8"))
RPM = float(_env("NARRA_RPM", default="0"))          # 0 = sin límite propio
REQ_TIMEOUT = float(_env("NARRA_TIMEOUT", default="45"))
DEADLINE_S = float(_env("NARRA_DEADLINE", default="300"))
_PRICES = {"grok-4.20-0309-non-reasoning": (1.25, 2.50)}  # docs.x.ai, oct 2026
PRICE_IN = float(_env("NARRA_PRICE_IN", default=str(_PRICES.get(MODEL, (0, 0))[0])))
PRICE_OUT = float(_env("NARRA_PRICE_OUT", default=str(_PRICES.get(MODEL, (0, 0))[1])))
MAX_ARTICLES = 20
SUMMARY_CHARS = 420
KEEP_HOURS = 72

SYSTEM = """You are the wire-desk editor of a neutral, non-partisan news app. You receive several reports about the same story from different news outlets (headline, RSS summary, outlet name, publication time). Write a short factual narrative of the whole story that combines all of them.

Rules:
- Use ONLY information explicitly present in the reports. Never add background knowledge, names, numbers, causes, consequences, quotes or predictions that are not in them. No speculation.
- Cover what happened, who, where and when (use the dates given; "today"/"yesterday" in a report refers to its own publication date), plus context only if the reports give it.
- Facts that several outlets report can be stated plainly. Claims, figures or details that only one outlet reports, or where outlets disagree, must be attributed: "según X" in Spanish / "according to X" in English. When outlets give different figures, say so and attribute each one.
- Attribute accusations, opinions and quotes to whoever made them. Neutral tone: no judgment words, no opinions, no sensationalism.
- 4 to 6 sentences per language, plain prose (no lists, no title, no headline repetition at the start). If the reports are thin, write fewer sentences (at least 2) rather than padding.
- If a report seems to be about a different event, ignore it.
- Do not mention "the reports", "the sources provided", the app or yourself.
- narrEs: natural Latin American Spanish. narrEn: natural English. Both must say the same thing. Keep outlet names exactly as given.

Answer with a JSON object with exactly two string keys: "narrEs" and "narrEn"."""

SCHEMA = {
    "type": "object",
    "properties": {"narrEs": {"type": "string"}, "narrEn": {"type": "string"}},
    "required": ["narrEs", "narrEn"],
    "additionalProperties": False,
}


def _h(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def story_urls(st) -> list[str]:
    return sorted({x["url"] for x in st.get("sources", []) if x.get("url")})


def story_key(st) -> str:
    return _h("\n".join(story_urls(st)))


def _cr_time(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(CR)
        return d.strftime("%Y-%m-%d %H:%M") + " (hora CR)"
    except Exception:
        return iso or "?"


# ---------------------------------------------------------------- IA ------------------

def pick_articles(st, texts: dict) -> list[dict]:
    """Una nota por medio (la de resumen más largo), hasta MAX_ARTICLES, en orden cronológico."""
    best = {}
    for x in st.get("sources", []):
        summ = (texts.get(x.get("url")) or "").strip()
        cur = best.get(x["source"])
        if cur is None or len(summ) > len(cur[1]):
            best[x["source"]] = (x, summ)
    rows = sorted(best.values(), key=lambda r: -len(r[1]))[:MAX_ARTICLES]
    rows.sort(key=lambda r: r[0].get("publishedAt", ""))
    return [{"source": x["source"], "lang": x.get("lang", "?"), "title": x.get("title", ""),
             "summary": s[:SUMMARY_CHARS], "publishedAt": x.get("publishedAt", "")} for x, s in rows]


def build_prompt(arts: list[dict], now: datetime) -> str:
    lines = [f"Today is {now.astimezone(CR).strftime('%Y-%m-%d')} (Costa Rica time).",
             f"The story was reported by {len(arts)} outlet(s):", ""]
    for i, a in enumerate(arts, 1):
        lines.append(f"[{i}] {a['source']} · {a['lang'].upper()} · {_cr_time(a['publishedAt'])}")
        lines.append(f"Headline: {a['title']}")
        if a["summary"] and a["summary"] != a["title"]:
            lines.append(f"Summary: {a['summary']}")
        lines.append("")
    return "\n".join(lines).strip()


def _thin(arts: list[dict]) -> bool:
    """Muy poco texto para narrar sin inventar (1 sola nota casi sin resumen)."""
    return len(arts) < 2 and sum(len(a["summary"]) for a in arts) < 80


class _Limiter:
    """Espacia el inicio de las solicitudes (para límites por minuto de planes gratis)."""
    def __init__(self, rpm: float):
        self.gap = 60.0 / rpm if rpm > 0 else 0.0
        self.next = 0.0
        self.lock = threading.Lock()

    def wait(self):
        if not self.gap:
            return
        with self.lock:
            now = time.time()
            at = max(now, self.next)
            self.next = at + self.gap
        if at > now:
            time.sleep(at - now)


_LIMIT = _Limiter(RPM)
_FMT = {"mode": "json_schema", "reasoning": REASONING}   # se degradan si el proveedor da 400
_HALT = threading.Event()          # plazo total vencido: no empezar más intentos


def _parse_content(content: str) -> dict:
    t = (content or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    return json.loads(t[i:j + 1] if i >= 0 and j > i else t)


def call_api(key: str, prompt: str) -> tuple[dict, dict]:
    last = "error"
    for attempt in range(4):
        if _HALT.is_set():
            raise RuntimeError("detenido (plazo o cuota)")
        mode, reasoning = _FMT["mode"], _FMT["reasoning"]
        body = {"model": MODEL, "temperature": 0.2, "max_tokens": 1400,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
        if reasoning:
            body["reasoning_effort"] = reasoning
        if mode == "json_schema":
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "narracion", "schema": SCHEMA, "strict": True}}
        else:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                     "User-Agent": "noticias-app/1.0"})
        _LIMIT.wait()
        try:
            with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8"))
            return _parse_content(data["choices"][0]["message"]["content"]), data.get("usage") or {}
        except urllib.error.HTTPError as e:   # el texto de HTTPError no incluye cabeceras (ni la clave)
            last = f"HTTP {e.code}"
            if e.code == 400 and mode == "json_schema":
                _FMT["mode"] = "json_object"       # el modelo no acepta json_schema
                continue
            if e.code == 400 and reasoning:
                _FMT["reasoning"] = ""             # ni reasoning_effort
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < 2 and not _HALT.is_set():
                try:
                    ra = float(e.headers.get("Retry-After") or 0)
                except Exception:
                    ra = 0
                time.sleep(min(20.0, max(ra, 3.0 * (attempt + 1))))
                continue
            raise RuntimeError(last) from None
        except (ValueError, KeyError, IndexError, TypeError):
            last = "respuesta no es JSON"
            if attempt < 1:
                continue
            raise RuntimeError(last) from None
        except Exception as e:
            last = type(e).__name__
            if attempt < 1:
                time.sleep(2)
                continue
            raise RuntimeError(last) from None
    raise RuntimeError(last)


def _clean(t) -> str | None:
    if not isinstance(t, str):
        return None
    t = " ".join(t.split())
    return t if 60 <= len(t) <= 2000 else None


# ----------------------------------------------------------- extracto sin IA ----------

_BOILER = re.compile(
    r"(The post .{3,160}? appeared first on .{2,80}?\.?$|\bLa entrada .{3,160}? (se public[oó]|aparece|apareció) primero en .{2,80}?\.?$"
    r"|\b(Leer|Seguir leyendo|Lee|Read|Continue reading|Read more|Más información|Ver más)\b.{0,40}$"
    r"|\[(…|\.\.\.|&#8230;)\]|\(Foto[^)]*\)|\bFoto:.*$)", re.I)
_SPLIT = re.compile(r"(?<=[.!?…»”\"])\s+(?=[«“\"¿¡(]?[A-ZÁÉÍÓÚÑÜ])")
_ABBR = re.compile(r"(\b[A-ZÁÉÍÓÚ]\.|\b(EE|UU|Sr|Sra|Dr|Dra|Lic|Ing|St|Mr|Mrs|Ms|Jr|Gral|Gob|No|núm|art|etc|vs|U\.S|a\.m|p\.m|Inc|Corp|Co|Ltd|Fr|Sen|Rep|Gov|Gen|Lt|Col|Prof|Pres|Sgt|Capt|Mt|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|ene|abr|ago|dic))\.?$")
_STOP = set("""el la los las un una unos unas de del al y o u en con por para sin sobre entre tras como que se su sus lo le les es son fue fueron ha han
este esta estos estas ese esa eso más menos muy ya pero también según desde hasta durante cuando donde mientras
the a an of to in on for and or but with by from at as is are was were be been has have had this that these those its their it
not no after before over into about than more less also said says will would could""".split())


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _fold(s)) if len(w) > 3 and w not in _STOP}


_CONNECT = re.compile(r"^(Además|Asimismo|Sin embargo|No obstante|Por otro lado|Por su parte|También|Mientras tanto|Por ello|Por eso|"
                      r"However|Meanwhile|Also|But|And|Still|Yet|Moreover|Instead|Separately|In addition)\b")
_SELF = re.compile(r"\b(our|nuestro|nuestra|nuestros) (news|podcast|newsletter|programa|show|edición|reporter|reporters|team)\b"
                   r"|\b(subscribe|suscr[ií]bete|click here|haz clic)\b", re.I)


def _sentences(summary: str, outlet: str = "") -> list[str]:
    s = _BOILER.sub("", " ".join((summary or "").split())).strip()
    parts, buf = [], ""
    for p in _SPLIT.split(s):
        buf = (buf + " " + p).strip() if buf else p
        if _ABBR.search(buf[:-1] if buf.endswith(".") else buf) and not buf.endswith(("?", "!")):
            continue
        parts.append(buf); buf = ""
    if buf:
        parts.append(buf)
    if parts and (s.endswith("…") or s.endswith("...") or _ABBR.search(parts[-1][:-1])):
        parts.pop()            # resumen cortado: la última frase está incompleta
    out = []
    for p in parts:
        p = p.strip()
        if not (45 <= len(p) <= 330) or len(p.split()) < 7:
            continue
        if not re.search(r"([.!][»”\"’)]?|[»”\"’)]\.)$", p) or not re.match(r"[«“\"¿¡(]?[A-ZÁÉÍÓÚÑÜ]", p):
            continue   # sin punto final (subtítulos), preguntas o fragmentos
        if "|" in p or "http" in p or p.startswith(("¿", "(")) or re.search(r"[.!?] [a-záéíóúñ]", p):
            continue   # texto pegado o roto
        if _CONNECT.match(p) or _SELF.search(p) or (outlet and p.startswith(outlet)):
            continue   # depende de una frase anterior, autopromoción o titular pegado
        out.append(p)
    return out


def _jacc(a: set, b: set) -> float:
    return len(a & b) / max(1, len(a | b))


def _overlap(a: set, b: set) -> float:
    """Parte de la frase más corta que ya está en la otra (para no repetir lo mismo)."""
    return len(a & b) / max(1, min(len(a), len(b)))


_LEAD = {"es": ["Según {o}, {s}", "De acuerdo con {o}, {s}"], "en": ["According to {o}, {s}"]}
_LEAD_KEEP = {"es": "{o} informa: {s}", "en": "{o} reports: {s}"}


_ARTICLES = set("el la los las un una unos unas este esta estos estas ese esa su sus the a an this these its his her their".split())


def _attribute(sent: str, outlet: str, lang: str, i: int, lower_ok: set) -> str:
    first = re.match(r"[«“\"¿¡(]?([A-Za-zÁÉÍÓÚÑÜáéíóúñü]+)", sent)
    w = first.group(1) if first else ""
    nxt = sent[first.end():].lstrip()[:1] if first else ""
    if w and not w.isupper() and _fold(w) in lower_ok and (not nxt.isupper() or _fold(w) in _ARTICLES):
        k = sent.find(w)
        s = sent[:k] + w[0].lower() + w[1:] + sent[k + len(w):]
        pats = _LEAD[lang]
        return pats[i % len(pats)].format(o=outlet, s=s)
    return _LEAD_KEEP[lang].format(o=outlet, s=sent)


def extract(st, texts: dict, lang: str, max_sent: int = 4, max_chars: int = 700):
    """Frases clave de varios medios (idioma `lang`), sin repetir y con atribución.
    Devuelve (texto, nº de medios) o (None, 0) si no hay al menos 2 medios con frases útiles."""
    rows = [x for x in st.get("sources", []) if x.get("lang") == lang]
    by_outlet: dict[str, list] = {}
    for x in rows:
        for j, s in enumerate(_sentences(texts.get(x.get("url")) or "", x["source"])):
            by_outlet.setdefault(x["source"], []).append((j, s))
    if len(by_outlet) < 2:
        return None, 0
    corpus_all = " ".join((x.get("title", "") + " " + (texts.get(x.get("url")) or "")) for x in st.get("sources", []))
    # palabras que aparecen en minúscula en algún texto (para «Según X, el …» sin romper nombres propios)
    lower_ok = {_fold(w) for w in re.findall(r"(?<![.!?]\s)\b([a-záéíóúñü]+)\b", corpus_all)}
    other_tok = {}
    for o in by_outlet:
        other = " ".join(x.get("title", "") + " " + (texts.get(x.get("url")) or "")
                         for x in st.get("sources", []) if x["source"] != o)
        other_tok[o] = _toks(other)
    head = _toks(st.get("headlineEs" if lang == "es" else "headlineEn") or st.get("headline") or "")
    scored = []
    for o, sents in by_outlet.items():
        seen = set()
        for j, s in sents:
            if s in seen:
                continue
            seen.add(s)
            t = _toks(s)
            if len(t) < 4:
                continue
            consensus = len(t & other_tok[o]) / len(t)       # lo que otros medios también dicen
            scored.append((consensus + (0.15 if j == 0 else 0) - 0.03 * j, o, s, t))
    scored.sort(key=lambda r: -r[0])
    chosen, used_o, total = [], [], 0
    for rnd in (0, 1):                     # 1.ª vuelta: una frase por medio; 2.ª: completar
        for sc, o, s, t in scored:
            if len(chosen) >= max_sent or (rnd == 0 and o in used_o):
                continue
            if sc < 0.25 or any(_overlap(t, c[3]) >= 0.5 for c in chosen) or len(t & head) / len(t) >= 0.75:
                continue
            if total + len(s) > max_chars and chosen:
                continue
            chosen.append((sc, o, s, t)); used_o.append(o); total += len(s)
    outlets = list(dict.fromkeys(used_o))
    if len(outlets) < 2:
        return None, 0
    # orden de lectura: primero la frase más compartida, luego por medio
    text = " ".join(_attribute(s, o, lang, i, lower_ok) for i, (_, o, s, _) in enumerate(chosen))
    return text, len(outlets)


def apply_extracts(groups: dict, texts: dict) -> int:
    n = 0
    for sts in groups.values():
        st = sts[0]
        if st.get("narrKind") == "ia":
            continue
        es, nes = extract(st, texts, "es")
        en, nen = extract(st, texts, "en")
        if not es and not en:
            continue
        n += 1
        for s in sts:
            s["narrKind"] = "extracto"
            if es:
                s["narrEs"], s["narrNEs"] = es, nes
            if en:
                s["narrEn"], s["narrNEn"] = en, nen
    return n


# --------------------------------------------------------------- general --------------

def load_cache() -> dict:
    try:
        d = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return d.get("entries", {}) if isinstance(d, dict) else {}
    except Exception:
        return {}


def _reusable(entry: dict, hashes: set[str]) -> bool:
    """Relato anterior de casi las mismas notas: crecimiento pequeño, nada (o casi nada) se fue."""
    old = set(entry.get("u", []))
    if not old:
        return False
    added, gone = len(hashes - old), len(old - hashes)
    return added <= max(2, len(old) // 4) and gone <= len(old) // 4 and len(old & hashes) >= 2


def narrate(cats: list[dict], texts: dict, now: datetime) -> dict:
    report = {"host": HOST, "model": MODEL, "stories": 0, "unique": 0, "ia": 0, "cached": 0,
              "reused": 0, "called": 0, "ok": 0, "failed": 0, "skippedThin": 0, "overCap": 0,
              "extracts": 0, "keyPresent": False, "tokensIn": 0, "tokensOut": 0, "seconds": 0.0}
    if _env("NARRAR", default="1") == "0":
        report["disabled"] = True
        return report
    t0 = time.time()
    key = _env("NARRA_API_KEY", "XAI_API_KEY")
    report["keyPresent"] = bool(key)
    cache = load_cache()
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    groups: dict[str, list] = {}           # historias únicas (pueden repetirse entre pestañas)
    for c in cats:
        for st in c.get("stories", []):
            report["stories"] += 1
            if st.get("sources"):
                groups.setdefault(story_key(st), []).append(st)
    report["unique"] = len(groups)

    def apply(k, entry):
        for st in groups[k]:
            st["narrKind"] = "ia"
            st["narrEs"], st["narrEn"], st["narrN"] = entry["es"], entry["en"], entry["n"]
            st.pop("narrNEs", None); st.pop("narrNEn", None)
        entry["used"] = now_iso

    todo = []
    for k, sts in groups.items():
        hashes = {_h(u) for u in story_urls(sts[0])}
        if k in cache:
            apply(k, cache[k]); report["cached"] += 1; continue
        near = next((e for e in cache.values() if _reusable(e, hashes)), None)
        if near is not None:
            if key:   # se registra con la nueva clave para la próxima corrida
                near = cache[k] = dict(near, u=sorted(hashes))
            apply(k, near); report["reused"] += 1; continue
        if not key:
            continue
        arts = pick_articles(sts[0], texts)
        if _thin(arts):
            report["skippedThin"] += 1; continue
        prio = (bool(sts[0].get("stale")), -len(arts), sts[0].get("id", ""))
        todo.append((prio, k, hashes, arts))

    todo.sort(key=lambda r: r[0])
    report["overCap"] = max(0, len(todo) - MAX_CALLS)
    todo = todo[:MAX_CALLS]
    if todo:
        ex = ThreadPoolExecutor(max_workers=WORKERS)
        futs = {ex.submit(call_api, key, build_prompt(arts, now)): (k, hashes, arts) for _, k, hashes, arts in todo}
        report["called"] = len(futs)
        errors: dict[str, int] = {}
        pending = set(futs)
        while pending:
            left = DEADLINE_S - (time.time() - t0)
            if left <= 0:
                break
            done, pending = wait(pending, timeout=left, return_when=FIRST_COMPLETED)
            for f in done:
                k, hashes, arts = futs[f]
                try:
                    out, usage = f.result()
                    es, en = _clean(out.get("narrEs")), _clean(out.get("narrEn"))
                    if not es or not en:
                        raise RuntimeError("respuesta vacía o inválida")
                    report["tokensIn"] += int(usage.get("prompt_tokens") or 0)
                    report["tokensOut"] += int(usage.get("completion_tokens") or 0)
                    cache[k] = {"es": es, "en": en, "n": len({a["source"] for a in arts}), "model": MODEL,
                                "at": now_iso, "u": sorted(hashes)}
                    apply(k, cache[k]); report["ok"] += 1
                except Exception as e:
                    msg = str(e)[:60]
                    errors[msg] = errors.get(msg, 0) + 1
                    report["failed"] += 1
                    if errors.get("HTTP 429", 0) >= 3 and not _HALT.is_set():
                        _HALT.set()                # cuota agotada (p. ej. límite diario gratis): no insistir
                        report["quotaStop"] = True
        if pending:
            _HALT.set()
            report["timedOut"] = len(pending)
            for f in pending:
                f.cancel()
        ex.shutdown(wait=False, cancel_futures=True)
        if errors:
            report["errors"] = errors
        report["responseFormat"] = _FMT["mode"]
        report["reasoning"] = _FMT["reasoning"] or None

    report["ia"] = sum(1 for sts in groups.values() if sts[0].get("narrKind") == "ia")
    try:
        report["extracts"] = apply_extracts(groups, texts)
    except Exception as e:   # el extracto nunca rompe nada
        report["extractError"] = type(e).__name__

    cutoff = (now - timedelta(hours=KEEP_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache = {k: e for k, e in cache.items() if e.get("used", e.get("at", "")) >= cutoff}
    if key or CACHE_PATH.exists():
        CACHE_PATH.write_text(json.dumps({"entries": cache}, ensure_ascii=False, indent=0, sort_keys=True),
                              encoding="utf-8")
    report["cacheEntries"] = len(cache)
    if PRICE_IN or PRICE_OUT:
        report["costUSD"] = round(report["tokensIn"] / 1e6 * PRICE_IN + report["tokensOut"] / 1e6 * PRICE_OUT, 4)
    report["seconds"] = round(time.time() - t0, 1)
    return report
