from datetime import datetime, timezone, timedelta
from actualizar import parse_date


def test_rfc2822_with_offset_becomes_utc():
    dt = parse_date("Thu, 14 Nov 2026 18:30:00 +0600")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt == datetime(2026, 11, 14, 12, 30, tzinfo=timezone.utc)


def test_iso_with_z():
    dt = parse_date("2026-11-14T15:00:00Z")
    assert dt == datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


def test_iso_with_offset():
    dt = parse_date("2026-11-14T12:00:00-06:00")
    assert dt == datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)


def test_naive_iso_is_treated_as_utc():
    """Comportamiento actual: si el feed no trae zona, se asume UTC.
    Un medio que publique hora local sin zona puede quedar corrido."""
    dt = parse_date("2026-11-14T12:00:00")
    assert dt == datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def test_invalid_returns_none():
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("no es una fecha") is None


def test_empty_whitespace_returns_none():
    assert parse_date("   ") is None
