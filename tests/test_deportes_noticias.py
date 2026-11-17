"""Arreglo 7: noticias deportivas de consenso además de los marcadores de ESPN."""
import deportes_noticias as D


def test_filtra_apuestas_en_vivo_y_donde_ver():
    for t in ["Saprissa vs Herediano: dónde ver y a qué hora", "Premier League odds, picks and best bets",
              "Real Madrid - Barcelona en directo, minuto a minuto", "Arsenal 2-1 Chelsea: player ratings",
              "Liverpool v Spurs: live", "Pronóstico y apuestas del clásico",
              "Argentina vs. Costa Rica: Hora y canales para ver hoy este partido",
              "Argentina vs. Costa Rica: estas son las opciones para ver el partido"]:
        assert D.SKIP.search(t), t


def test_deja_pasar_noticias():
    for t in ["Costa Rica queda eliminada del Mundial tras empatar con Honduras",
              "Carlo Ancelotti anuncia la lista de Brasil", "Ohtani wins third MVP award",
              "Liverpool sack manager after run of defeats"]:
        assert not D.SKIP.search(t), t


def test_feeds_sin_duplicados_y_https():
    ids = [f[0] for f in D.SPORT_FEEDS]
    assert len(ids) == len(set(ids))
    for f in D.SPORT_FEEDS:
        assert f[1].startswith("https://") or f[1].startswith("gn:")
    assert D.MIN_OUTLETS == 3


def test_build_agrupa_por_consenso(monkeypatch):
    from datetime import datetime, timezone
    now = datetime(2026, 11, 17, 18, tzinfo=timezone.utc)
    d = "Tue, 17 Nov 2026 15:00:00 GMT"
    rows = {
        "dep-bbc": [("Costa Rica eliminated from World Cup qualifying after Honduras draw", "https://www.bbc.com/sport/a1", d, "")],
        "dep-guardian": [("Costa Rica eliminated from World Cup qualifying after draw with Honduras", "https://www.theguardian.com/a1", d, "")],
        "dep-sky": [("Honduras draw sees Costa Rica eliminated from World Cup qualifying", "https://www.skysports.com/a1", d, "")],
        "dep-cbs": [("Ohtani wins third MVP award in unanimous vote", "https://www.cbssports.com/a2", d, "")],
        "dep-fox": [("Shohei Ohtani wins third MVP award unanimous vote", "https://www.foxsports.com/a2", d, "")],
    }
    monkeypatch.setattr(D, "fetch", lambda f: (f, rows.get(f[0]), None if f[0] in rows else "sin ítems"))
    import time
    bg = [{"title": f"Parliament votes on budget bill number {i} amid protests", "summary": "", "lang": "en",
           "url": f"https://x.test/{i}", "_ts": time.time()} for i in range(120)]
    stories, cands, rep = D.build(now, bg)
    assert len(stories) == 1 and stories[0]["outlets"] == 3
    assert len(cands) == 1
    assert rep["stories"] == 1 and rep["candidates"] == 1
