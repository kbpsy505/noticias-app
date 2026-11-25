"""Sismos sentidos de la Red Sismológica Nacional (RSN, UCR-ICE) para el encabezado.

Fuente, sin llave ni registro: el RSS oficial de «Últimos sismos»
(https://rsn.ucr.ac.cr/actividad-sismica/ultimos-sismos?format=feed&type=rss).
Esos informes son, en la práctica, sismos ya revisados y reportados como sentidos;
aquí se descarta cualquier ítem que no lo diga. Las magnitudes se guardan en Mw,
tal cual las publica la RSN: no se mezclan con Ml (OVSICORI) ni mb (USGS).

Se ejecuta con cada actualización (cada ~3 h) y guarda una foto en noticias.json
→ sismos. La app, al abrir, pide el mismo RSS cada 5 min y, si falla, muestra
esta foto con la hora. Nunca rompe la actualización de noticias.
"""
from __future__ import annotations

import re
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree as ET

UA = "Mozilla/5.0 (compatible; noticias-app; +https://kbpsy505.github.io/noticias-app/)"
RSS_URL = "https://rsn.ucr.ac.cr/actividad-sismica/ultimos-sismos?format=feed&type=rss"
SOURCE = "Red Sismológica Nacional (UCR-ICE)"
SOURCE_URL = "https://rsn.ucr.ac.cr/actividad-sismica/ultimos-sismos"
CR = timezone(timedelta(hours=-6))  # Costa Rica no usa horario de verano
MAX_EVENTS = 8
MAX_BYTES = 1_000_000

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
# <strong>Fecha: </strong>25 de noviembre del 2026.
FIELD_RE = re.compile(r"<strong>\s*([^<:]+):\s*</strong>\s*([^<]*)", re.I)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
# SISMO, 25 de noviembre del 2026, 10:14 am., Mag: 4,1 Mw, SENTIDO
TITLE_RE = re.compile(
    r"SISMO,\s*(.+?),\s*(\d{1,2}:\d{2}\s*[ap]\.?\s*m\.?)\.?,?\s*Mag:\s*([\d.,]+)\s*([A-Za-z]+)?",
    re.I,
)
FECHA_RE = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+del?\s+(\d{4})",
    re.I,
)
HORA_RE = re.compile(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m", re.I)
NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def local(tag: str) -> str:
    return tag.split("}", 1)[-1].lower() if tag else ""


def clean(text: str) -> str:
    text = TAG_RE.sub(" ", unescape(text or ""))
    return SPACE_RE.sub(" ", text).strip(" \t\n\r.,;")


def comma_float(text: str):
    m = NUM_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def fields_from_html(html: str) -> dict:
    out = {}
    for key, val in FIELD_RE.findall(html or ""):
        k = clean(key).lower()
        v = clean(val)
        if k and v:
            out[k] = v
    return out


def parse_fecha_hora(fecha: str, hora: str):
    if not fecha or not hora:
        return None
    fm = FECHA_RE.search(fecha)
    hm = HORA_RE.search(hora)
    if not fm or not hm:
        return None
    month = MONTHS.get(fm.group(2).lower())
    if not month:
        return None
    hour, minute = int(hm.group(1)), int(hm.group(2))
    if hm.group(3).lower() == "p" and hour != 12:
        hour += 12
    if hm.group(3).lower() == "a" and hour == 12:
        hour = 0
    try:
        return datetime(int(fm.group(3)), month, int(fm.group(1)), hour, minute, tzinfo=CR)
    except ValueError:
        return None


def parse_pubdate(text: str):
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_felt(title: str, fields: dict, plain: str) -> bool:
    if re.search(r"\bSENTIDO\b", title or "", re.I):
        return True
    intens = fields.get("intensidades") or ""
    if re.search(r"sentido\s+en", intens, re.I):
        return True
    if re.search(r"sentido\s+en", plain or "", re.I):
        return True
    return False


def felt_in(fields: dict, plain: str) -> str:
    intens = fields.get("intensidades") or ""
    m = re.search(r"sentido\s+en:\s*(.+)", intens, re.I)
    if m:
        return clean(m.group(1))
    m = re.search(r"sentido\s+en:\s*(.+)", plain or "", re.I)
    return clean(m.group(1)) if m else ""


def parse_coords(text: str):
    if not text:
        return None, None
    # Las coordenadas de la RSN usan coma decimal: "10,253 y -84,374".
    parts = re.split(r"\s+y\s+", text, maxsplit=1)
    if len(parts) != 2:
        return None, None
    return comma_float(parts[0]), comma_float(parts[1])


def iso_utc(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_cr(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(CR).strftime("%Y-%m-%dT%H:%M:%S-06:00")


def event_from_item(title: str, link: str, guid: str, desc: str, pub: str) -> dict | None:
    fields = fields_from_html(desc)
    plain = clean(desc)
    title = clean(title)
    if not is_felt(title, fields, plain):
        return None
    tm = TITLE_RE.search(title)
    fecha = fields.get("fecha") or (tm.group(1) if tm else "")
    hora = fields.get("hora local") or fields.get("hora") or (tm.group(2) if tm else "")
    occurred = parse_fecha_hora(fecha, hora)
    published = parse_pubdate(pub)
    mag = comma_float(fields.get("magnitud") or (tm.group(3) if tm else "") or "")
    mag_type = (fields.get("magnitud") or "")
    mt = re.search(r"\b(Mw|ML|Ml|mb|Mww|mB)\b", mag_type, re.I)
    if not mt and tm and tm.group(4):
        mt_s = tm.group(4)
    else:
        mt_s = mt.group(1) if mt else "Mw"
    # Solo Mw de la RSN. Si un ítem viniera en otra escala, no se mezcla: se omite.
    if mt_s.lower() != "mw":
        return None
    loc = fields.get("localización") or fields.get("localizacion") or ""
    lat, lon = parse_coords(fields.get("coordenadas") or "")
    depth = comma_float(fields.get("profundidad") or "")
    url = (link or guid or "").strip()
    if url and not (url.startswith("http://") or url.startswith("https://")):
        url = ""
    ev = {
        "id": (guid or url or title)[:200],
        "title": title,
        "url": url,
        "occurredAt": iso_utc(occurred) or iso_utc(published),
        "occurredLocal": iso_cr(occurred) or iso_cr(published.astimezone(CR) if published else None),
        "magnitude": mag,
        "magnitudeType": "Mw",
        "location": loc,
        "latitude": lat,
        "longitude": lon,
        "depthKm": depth,
        "felt": True,
        "feltIn": felt_in(fields, plain),
        "origin": fields.get("origen") or "",
        "reviewed": "revisada" in plain.lower(),
        "publishedAt": iso_utc(published),
    }
    if ev["magnitude"] is None or not ev["occurredAt"]:
        return None
    return ev


def iter_entries(root: ET.Element):
    for el in root.iter():
        if local(el.tag) in ("item", "entry"):
            yield el


def child_text(item: ET.Element, names: tuple[str, ...]) -> str:
    for ch in list(item):
        if local(ch.tag) in names:
            href = (ch.get("href") or "").strip()
            text = unescape("".join(ch.itertext()).strip())
            if href and not text:
                return href
            return href or text
    return ""


def parse_rss(xml_bytes: bytes) -> list[dict]:
    """Parsea RSS o Atom y devuelve solo sismos sentidos en Mw, más nuevos primero."""
    if not xml_bytes:
        return []
    root = ET.fromstring(xml_bytes)
    events, seen = [], set()
    for item in iter_entries(root):
        title = child_text(item, ("title",))
        link = child_text(item, ("link",))
        guid = child_text(item, ("guid", "id"))
        desc = ""
        for ch in list(item):
            if local(ch.tag) in ("description", "summary", "content"):
                desc = "".join(ch.itertext())
                break
        pub = child_text(item, ("pubdate", "published", "updated"))
        ev = event_from_item(title, link, guid, desc, pub)
        if ev is None:
            continue
        key = ev["id"] or ev["occurredAt"]
        if key in seen:
            continue
        seen.add(key)
        events.append(ev)
    events.sort(key=lambda e: e.get("occurredAt") or "", reverse=True)
    return events


def fetch_rss(url: str = RSS_URL) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("respuesta demasiado grande")
    return data


def empty_payload() -> dict:
    return {
        "source": SOURCE,
        "sourceUrl": SOURCE_URL,
        "feedUrl": RSS_URL,
        "fetchedAt": None,
        "events": [],
    }


def build(now, previous=None):
    """Devuelve (sismos, informe). Si el feed falla, reutiliza la foto anterior."""
    out, report = empty_payload(), {}
    try:
        xml = fetch_rss()
        events = parse_rss(xml)
        out["events"] = events[:MAX_EVENTS]
        out["fetchedAt"] = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        report.update(ok=len(events), shown=len(out["events"]))
        return out, report
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
    prev = (previous or {}).get("sismos") if isinstance(previous, dict) else None
    if isinstance(prev, dict) and prev.get("events"):
        reused = dict(prev)
        reused["stale"] = True
        report["reusedPrevious"] = True
        return reused, report
    return out, report
