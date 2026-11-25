"""Parser y foto de sismos de la RSN (sin red, salvo que se parchee el fetch)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sismos

FIX = Path(__file__).parent / "fixtures" / "rsn-ultimos-sismos.xml"


def _xml() -> bytes:
    return FIX.read_bytes()


def test_parse_felt_mw_fields_and_comma_decimals():
    evs = sismos.parse_rss(_xml())
    ids = [e["location"] for e in evs]
    assert "5 km al Noreste de Tapesco, Zarcero" in ids
    assert "5 km al Sur de Laurel, Corredores" in ids
    assert "4 km al Sur de Cachi, Paraiso, Cartago" in ids
    # El no sentido y el de Ml no entran.
    assert len(evs) == 3
    z = evs[0]
    assert z["magnitude"] == 4.1
    assert z["magnitudeType"] == "Mw"
    assert z["depthKm"] == 4.0
    assert z["latitude"] == 10.253
    assert z["longitude"] == -84.374
    assert z["felt"] is True
    assert z["feltIn"] == "Ciudad Quesada, Zarcero y Bajos del Toro"
    assert z["reviewed"] is True
    assert z["occurredLocal"] == "2026-11-25T10:14:00-06:00"
    assert z["occurredAt"] == "2026-11-25T16:14:00Z"
    assert z["url"].startswith("https://rsn.ucr.ac.cr/")
    assert "Fallamiento" in z["origin"]


def test_sorts_newest_first_and_parses_early_morning():
    evs = sismos.parse_rss(_xml())
    times = [e["occurredAt"] for e in evs]
    assert times == sorted(times, reverse=True)
    cachi = next(e for e in evs if "Cachi" in e["location"])
    assert cachi["occurredLocal"] == "2026-11-16T02:07:00-06:00"


def test_drops_unfelt_and_non_mw_and_javascript_url():
    evs = sismos.parse_rss(_xml())
    urls = [e["url"] for e in evs]
    mags = [e["magnitudeType"] for e in evs]
    assert all(e["felt"] for e in evs)
    assert all(t == "Mw" for t in mags)
    assert all(not u.startswith("javascript:") for u in urls)
    assert not any("Cabo Blanco" in (e["location"] or "") for e in evs)
    assert not any(e["magnitude"] == 3.1 for e in evs)


def test_caps_at_eight(tmp_path):
    item = """
    <item>
      <title>SISMO, {d:02d} de noviembre del 2026, 1:00 pm., Mag: 3,0 Mw, SENTIDO</title>
      <link>https://rsn.ucr.ac.cr/s/{d}</link>
      <guid>https://rsn.ucr.ac.cr/s/{d}</guid>
      <description><![CDATA[<p><strong>Fecha: </strong>{d:02d} de noviembre del 2026.</p><p><strong>Hora Local: </strong>1:00 pm.</p><p><strong>Localización: </strong>lugar {d}</p><p><strong>Magnitud: </strong>3,0 Mw.</p><p><strong>Intensidades:</strong> Sentido en: un pueblo.</p>]]></description>
      <pubDate>Wed, {d:02d} Nov 2026 19:00:00 +0000</pubDate>
    </item>
    """
    body = "<?xml version='1.0'?><rss><channel>" + "".join(item.format(d=d) for d in range(1, 11)) + "</channel></rss>"
    evs = sismos.parse_rss(body.encode())
    assert len(evs) == 10
    sliced = evs[: sismos.MAX_EVENTS]
    assert len(sliced) == 8
    assert sliced[0]["location"] == "lugar 10"
    assert sliced[-1]["location"] == "lugar 3"


def test_build_uses_fetch_and_records_fetched_at(monkeypatch):
    monkeypatch.setattr(sismos, "fetch_rss", lambda: _xml())
    now = datetime(2026, 11, 25, 21, 10, tzinfo=timezone.utc)
    out, report = sismos.build(now)
    assert report["ok"] == 3
    assert report["shown"] == 3
    assert out["fetchedAt"] == "2026-11-25T21:10:00Z"
    assert out["source"] == "Red Sismológica Nacional (UCR-ICE)"
    assert out["sourceUrl"].startswith("https://rsn.ucr.ac.cr/")
    assert out["events"][0]["magnitude"] == 4.1
    assert "stale" not in out


def test_build_reuses_previous_when_feed_fails(monkeypatch):
    def boom():
        raise TimeoutError("feed caído")

    monkeypatch.setattr(sismos, "fetch_rss", boom)
    prev = {"sismos": {"source": "Red Sismológica Nacional (UCR-ICE)", "events": [{"magnitude": 4.1, "felt": True, "magnitudeType": "Mw"}], "fetchedAt": "2026-11-25T18:00:00Z"}}
    out, report = sismos.build(datetime.now(timezone.utc), previous=prev)
    assert report["reusedPrevious"] is True
    assert "TimeoutError" in report["error"]
    assert out["stale"] is True
    assert out["events"][0]["magnitude"] == 4.1


def test_build_empty_when_feed_fails_without_previous(monkeypatch):
    monkeypatch.setattr(sismos, "fetch_rss", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    out, report = sismos.build(datetime.now(timezone.utc), previous=None)
    assert out["events"] == []
    assert out["fetchedAt"] is None
    assert "error" in report
    assert "reusedPrevious" not in report
