"""Utilidades de prueba. No forman parte de la app en vivo."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

APP_HINT = "mundo"


def rfc2822(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt.astimezone(timezone.utc))


def recent(hours: float = 2.0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def rss_feed(items: list[dict]) -> bytes:
    """items: title, link, date (datetime|str), description?"""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        "<title>Fixture</title>",
    ]
    for it in items:
        date = it.get("date")
        if isinstance(date, datetime):
            date = rfc2822(date)
        elif not date:
            date = rfc2822(recent())
        desc = it.get("description", it["title"])
        parts.append("<item>")
        parts.append(f"<title>{it.get('title_raw', escape(it['title']))}</title>")
        parts.append(f"<link>{it.get('link_raw', escape(it['link']))}</link>")
        parts.append(f"<pubDate>{escape(str(date))}</pubDate>")
        parts.append(f"<description>{it.get('description_raw', escape(desc))}</description>")
        parts.append("</item>")
    parts.append("</channel></rss>")
    return "\n".join(parts).encode("utf-8")


def atom_feed(items: list[dict]) -> bytes:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        "<title>Fixture Atom</title>",
    ]
    for it in items:
        date = it.get("date")
        if isinstance(date, datetime):
            date = date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif not date:
            date = recent().strftime("%Y-%m-%dT%H:%M:%SZ")
        desc = it.get("description", it["title"])
        parts.append("<entry>")
        parts.append(f"<title>{escape(it['title'])}</title>")
        parts.append(f'<link href="{escape(it["link"])}"/>')
        parts.append(f"<published>{escape(str(date))}</published>")
        parts.append(f"<summary>{escape(desc)}</summary>")
        parts.append("</entry>")
    parts.append("</feed>")
    return "\n".join(parts).encode("utf-8")


def pool_item(title, org, *, source=None, lang="es", hours_ago=1.0, summary="",
              category="politica", path="story"):
    pub = recent(hours_ago)
    src = source or org
    slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower())[:60]
    return {
        "title": title,
        "url": f"https://{org}.example.com/{path}/{slug}",
        "source": src,
        "org": org,
        "lang": lang,
        "summary": summary or (title + ". Más detalles en el reporte del medio."),
        "category": category,
        "feed": org,
        "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_ts": pub.timestamp(),
    }
