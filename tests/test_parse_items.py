import gzip
from datetime import datetime, timezone
import pytest
from actualizar import parse_items, fetch_feed, FEEDS
from helpers import rss_feed, atom_feed, recent


def test_parses_rss_title_link_date_description():
    xml = rss_feed([{
        "title": "Un titular suficientemente largo de prueba",
        "link": "https://example.com/n1",
        "description": "Resumen de la nota de prueba.",
        "date": recent(1),
    }])
    items = parse_items(xml)
    assert len(items) == 1
    title, link, date_s, desc = items[0]
    assert title == "Un titular suficientemente largo de prueba"
    assert link == "https://example.com/n1"
    assert "Resumen" in desc
    assert date_s


def test_parses_atom_link_href():
    xml = atom_feed([{
        "title": "Atom headline that is long enough",
        "link": "https://example.com/atom-1",
        "description": "Atom summary text for the entry.",
    }])
    items = parse_items(xml)
    assert len(items) == 1
    assert items[0][0] == "Atom headline that is long enough"
    assert items[0][1] == "https://example.com/atom-1"


def test_parses_news_sitemap():
    xml = b'''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://crhoy.example/nota-larga</loc>
    <news:news>
      <news:title>Titular de sitemap lo bastante largo</news:title>
      <news:publication_date>2026-11-14T12:00:00Z</news:publication_date>
    </news:news>
  </url>
</urlset>
'''
    items = parse_items(xml)
    assert items[0][0] == "Titular de sitemap lo bastante largo"
    assert items[0][1] == "https://crhoy.example/nota-larga"
    assert "2026-11-14" in items[0][2]


def test_broken_xml_raises():
    with pytest.raises(Exception):
        parse_items(b"<rss><channel><item><title>sin cerrar")


def test_html_in_title_is_flattened():
    xml = rss_feed([{
        "title": "x",
        "title_raw": "Alerta <b>importante</b> en la region",
        "link": "https://example.com/h",
        "description": "desc",
    }])
    title, *_ = parse_items(xml)[0]
    assert title == "Alerta importante en la region"
    assert "<b>" not in title


def test_xxe_external_entity_is_not_expanded():
    """Las declaraciones de entidades se rechazan antes de parsear."""
    xml = b'''<?xml version="1.0"?>
<!DOCTYPE r [<!ENTITY xxe SYSTEM "file:///etc/hostname">]>
<rss><channel><item>
  <title>&xxe; no deberia leer el disco</title>
  <link>https://example.com/xxe</link>
</item></channel></rss>
'''
    with pytest.raises(ValueError):
        parse_items(xml)


def test_internal_entities_are_capped():
    xml = b'''<?xml version="1.0"?>
<!DOCTYPE r [
<!ENTITY a "aaaaaaaaaa">
<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
<!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">
]>
<rss><channel><item>
  <title>&d;</title>
  <link>https://example.com/bomb</link>
</item></channel></rss>
'''
    with pytest.raises(ValueError):
        parse_items(xml)


def test_simple_doctype_without_internal_subset_still_parses():
    xml = b'''<?xml version="1.0"?>
<!DOCTYPE rss PUBLIC "-//Netscape Communications//DTD RSS 0.91//EN" "http://my.netscape.com/publish/formats/rss-0.91.dtd">
<rss version="0.91"><channel><item>
  <title>Titular de prueba con doctype simple</title>
  <link>https://example.com/ok</link>
</item></channel></rss>
'''
    assert parse_items(xml)[0][1] == "https://example.com/ok"


def test_fetch_feed_returns_error_on_broken_xml_without_raising():
    feed = ("fx-broken", "https://example.invalid/rss.xml", "Broken", "broken", "es", None)

    def fake_fetch(url, simple=False):
        return b"<rss><channel><item><title>roto"

    import actualizar
    original = actualizar.fetch
    actualizar.fetch = fake_fetch
    # Evitar el fallback a curl (subprocess) parcheando run para que "falle"
    import subprocess
    orig_run = subprocess.run

    def no_curl(*a, **k):
        raise RuntimeError("curl disabled in tests")

    subprocess.run = no_curl
    try:
        f, rows, err = fetch_feed(feed)
        assert rows is None
        assert err
        assert "Parse" in err or "Syntax" in err or "Error" in err or "Runtime" in err
    finally:
        actualizar.fetch = original
        subprocess.run = orig_run
