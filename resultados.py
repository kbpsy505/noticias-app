"""Resultados deportivos para la pestaña Deportes (marcadores, no noticias).

Fuente, sin llave ni registro: los marcadores públicos de ESPN
(https://site.api.espn.com/apis/site/v2/sports/<deporte>/<liga>/scoreboard), los mismos que usa
espn.com. Cubren NFL, fútbol americano universitario (CFB), NBA, baloncesto universitario (CBB),
MLB, NHL, tenis (ATP y WTA) y UFC. Los sitios oficiales (nfl.com, nba.com, ncaa.com, nhl.com,
mlb.com) y Flashscore arman sus marcadores con JavaScript y feeds internos firmados, así que no se
leen de forma fiable desde GitHub Actions; en la app se enlazan como «ver en el sitio oficial».

Se ejecuta con cada actualización (cada ~3 h): los partidos «en juego» son una foto del momento de
la actualización, no un marcador en vivo. Si una liga falla queda vacía con su motivo; si fallan
todas, se devuelve None y la app solo muestra un aviso. Nunca rompe la actualización de noticias.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (compatible; noticias-app; +https://kbpsy505.github.io/noticias-app/)"
BASE = "https://site.api.espn.com/apis/site/v2/sports/"
CR = timezone(timedelta(hours=-6))   # Costa Rica no usa horario de verano
TENNIS_WINDOW_H = 30                 # partidos de tenis de ±30 h alrededor de la actualización
TENNIS_MAX = 24                      # por circuito

# mode: "week" = marcador por defecto (semana en curso); "days" = ayer, hoy y mañana (hora CR).
LEAGUES = [
    {"id": "nfl", "label": "NFL", "name": "NFL", "path": "football/nfl", "mode": "week",
     "official": "https://www.nfl.com/scores/", "officialName": "nfl.com"},
    # CFB: groups=80 = todos los juegos FBS de la semana (el marcador por defecto de ESPN solo trae los del
    # Top 25). La app muestra Top 25 por defecto (filtrando los partidos con un equipo rankeado) y
    # «show all games» con la lista completa.
    {"id": "cfb", "label": "CFB", "name": "Fútbol americano universitario (FBS)", "path": "football/college-football",
     "query": "?groups=80", "mode": "week", "official": "https://www.ncaa.com/scoreboard/football/fbs", "officialName": "ncaa.com"},
    {"id": "nba", "label": "NBA", "name": "NBA", "path": "basketball/nba", "mode": "days",
     "official": "https://www.nba.com/games", "officialName": "nba.com"},
    {"id": "cbb", "label": "CBB", "name": "Baloncesto universitario masculino", "path": "basketball/mens-college-basketball",
     "mode": "days", "official": "https://www.ncaa.com/scoreboard/basketball-men/d1", "officialName": "ncaa.com"},
    {"id": "mlb", "label": "MLB", "name": "MLB", "path": "baseball/mlb", "mode": "days",
     "official": "https://www.mlb.com/scores", "officialName": "mlb.com"},
    {"id": "nhl", "label": "NHL", "name": "NHL", "path": "hockey/nhl", "mode": "days",
     "official": "https://www.nhl.com/scores", "officialName": "nhl.com"},
    {"id": "tenis", "label": "Tenis", "name": "Tenis (ATP y WTA, individuales)", "path": None, "mode": "tennis",
     "official": "https://www.flashscore.com/tennis/", "officialName": "flashscore.com"},
    {"id": "mma", "label": "MMA", "name": "MMA (UFC)", "path": "mma/ufc", "mode": "mma",
     "official": "https://www.flashscore.com/mma/", "officialName": "flashscore.com"},
]

ORD = {1: "1.º", 2: "2.º", 3: "3.º", 4: "4.º"}
ROUNDS = {"Round 1": "1.ª ronda", "Round 2": "2.ª ronda", "Round 3": "3.ª ronda", "Round 4": "4.ª ronda",
          "Round of 16": "Octavos", "Quarterfinal": "Cuartos de final", "Quarterfinals": "Cuartos de final",
          "Semifinal": "Semifinal", "Semifinals": "Semifinal", "Final": "Final"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch(url):
    err = None
    for attempt in range(3):
        try:
            return get(url), None
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    return None, err


def _num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


def status_es(st, sport):
    """Estado del partido en español a partir del bloque status de ESPN."""
    t = st.get("type") or {}
    name, state = t.get("name", ""), t.get("state", "")
    short = t.get("shortDetail") or t.get("detail") or ""
    period, clock = st.get("period") or 0, st.get("displayClock") or ""
    special = {"STATUS_POSTPONED": "Pospuesto", "STATUS_CANCELED": "Cancelado", "STATUS_SUSPENDED": "Suspendido",
               "STATUS_DELAYED": "Retrasado", "STATUS_RAIN_DELAY": "Retrasado por lluvia",
               "STATUS_FORFEIT": "Forfeit", "STATUS_WALKOVER": "Walkover (W.O.)", "STATUS_RETIRED": "Final (retiro)",
               "STATUS_ABANDONED": "Abandonado", "STATUS_HALFTIME": "Medio tiempo",
               "STATUS_END_PERIOD": "Fin del periodo"}
    if name in special:
        if name == "STATUS_END_PERIOD" and sport == "football":
            return "Fin del " + ORD.get(period, f"{period}.º") + " cuarto"
        if name == "STATUS_END_PERIOD" and sport == "hockey":
            return "Intermedio"
        return special[name]
    if state == "post":
        extra = ""
        if re.search(r"/(\d+)$", short) and sport == "baseball":
            extra = " (" + re.search(r"/(\d+)$", short).group(1) + " entradas)"
        elif "SO" in short:
            extra = " (penales)"
        elif "OT" in short:
            extra = " (tiempo extra)"
        return "Final" + extra
    if state == "in":
        if sport == "baseball":
            m = re.match(r"(Top|Bot|Bottom|Mid|End)\w*\s+(\d+)", short)
            if m:
                half = {"Top": "Alta", "Bot": "Baja", "Bottom": "Baja", "Mid": "Mitad", "End": "Fin"}[m.group(1)]
                return f"{half} {m.group(2)}.ª"
            return "En juego"
        if sport == "mma":
            return f"En curso · {period}.º asalto" if period else "En curso"
        if sport == "tennis":
            return "En juego"
        unit = {"football": "cuarto", "basketball": "cuarto" if period <= 4 else "", "hockey": "periodo"}.get(sport, "")
        if sport == "basketball" and "college" in short.lower():
            unit = "tiempo"
        if (sport == "basketball" and period > 4) or (sport == "football" and period > 4) or (sport == "hockey" and period > 3):
            p = "Tiempo extra"
        else:
            p = ORD.get(period, f"{period}.º") + " " + unit
        return (p + (" · " + clock if clock and clock not in ("0:00", "0.0") else "")).strip()
    return ""   # programado: la app muestra la hora en CR


def team_side(c):
    t = c.get("team") or {}
    rec = next((r.get("summary") for r in (c.get("records") or []) if r.get("type") == "total" or r.get("name") == "overall"), None)
    rank = (c.get("curatedRank") or {}).get("current")
    return {
        "name": t.get("shortDisplayName") or t.get("displayName") or t.get("name") or "?",
        "full": t.get("displayName"),
        "abbr": t.get("abbreviation"),
        "logo": t.get("logo"),
        "score": c.get("score") if c.get("score") not in (None, "") else None,
        "winner": c.get("winner"),
        "record": rec,
        "rank": rank if isinstance(rank, int) and 0 < rank <= 25 else None,
        "home": c.get("homeAway") == "home",
    }


def _american(v):
    """«-162» → -162, «+136» → 136, «EVEN» → 100; None si no es una cuota americana."""
    if v is None:
        return None
    t = str(v).strip().upper()
    if t in ("EVEN", "EV", "PK"):
        return 100
    m = re.fullmatch(r"([+-]?)(\d{3,5})", t)
    if not m:
        return None
    n = int(m.group(2))
    return -n if m.group(1) == "-" else n


def _implied(o):
    """Probabilidad implícita de una cuota americana (con margen de la casa)."""
    if o is None or o == 0:
        return None
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def _close(side):
    """Línea vigente (close) o, si falta, la de apertura."""
    side = side or {}
    return side.get("close") or side.get("current") or side.get("open") or {}


SPREAD_NAMES = {"baseball": "Run line", "hockey": "Puck line"}


def parse_odds(comp, sport):
    """Líneas del mercado de ESPN (proveedor: casi siempre DraftKings) en un formato corto.

    Favorito del mercado = el lado con la cuota de moneyline más baja; su probabilidad se da sin el
    margen de la casa (normalizada entre los dos lados). Sin moneyline se usa el hándicap.
    No es una predicción propia ni un consejo de apuesta: es lo que dice el mercado.
    """
    lst = comp.get("odds") or []
    if not lst:
        return None
    o = sorted(lst, key=lambda x: (x.get("provider") or {}).get("priority", 99))[0]
    ml = o.get("moneyline") or {}
    ps = o.get("pointSpread") or {}
    tot = o.get("total") or {}
    ml_a, ml_h = _american(_close(ml.get("away")).get("odds")), _american(_close(ml.get("home")).get("odds"))
    sp_a, sp_h = _close(ps.get("away")), _close(ps.get("home"))
    ov, un = _close(tot.get("over")), _close(tot.get("under"))
    total_line = _num(o.get("overUnder"))
    if total_line is None and ov.get("line"):
        total_line = _num(str(ov["line"]).lstrip("ou"))
    out = {
        "provider": (o.get("provider") or {}).get("displayName") or (o.get("provider") or {}).get("name"),
        "details": o.get("details"),
        "ml": {"away": ml_a, "home": ml_h} if (ml_a is not None or ml_h is not None) else None,
        "spread": {"name": SPREAD_NAMES.get(sport, "Spread"),
                   "away": {"line": sp_a.get("line"), "odds": _american(sp_a.get("odds"))},
                   "home": {"line": sp_h.get("line"), "odds": _american(sp_h.get("odds"))}} if (sp_a.get("line") or sp_h.get("line")) else None,
        "total": {"line": total_line, "over": _american(ov.get("odds")), "under": _american(un.get("odds"))} if total_line is not None else None,
        "fav": None, "favProb": None,
    }
    pa, ph = _implied(ml_a), _implied(ml_h)
    if pa and ph:
        if abs(pa - ph) < 0.005:
            out["fav"] = "even"
        else:
            out["fav"] = "away" if pa > ph else "home"
            out["favProb"] = round(100 * max(pa, ph) / (pa + ph))
    else:  # sin moneyline: el lado que da puntos de ventaja (línea negativa)
        la, lh = _num(str(sp_a.get("line") or "").replace("+", "")), _num(str(sp_h.get("line") or "").replace("+", ""))
        if la is not None and la < 0:
            out["fav"] = "away"
        elif lh is not None and lh < 0:
            out["fav"] = "home"
        elif la == 0 or lh == 0:
            out["fav"] = "even"
    if not (out["ml"] or out["spread"] or out["total"]):
        return None
    return out


def team_games(data, sport):
    games = []
    for e in (data or {}).get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        st = comp.get("status") or e.get("status") or {}
        sides = sorted((team_side(c) for c in comp.get("competitors", [])), key=lambda s: s["home"])  # visitante arriba
        if len(sides) != 2:
            continue
        link = next((l.get("href") for l in e.get("links", []) if "summary" in (l.get("rel") or [])), None)
        notes = [n.get("headline") for n in comp.get("notes", []) if n.get("headline")]
        bc = ", ".join(n for b in comp.get("broadcasts", []) for n in b.get("names", []))
        state = (st.get("type") or {}).get("state", "pre")
        if state == "pre":
            for sd in sides:
                sd["score"] = None
        games.append({
            "id": e.get("id"),
            "start": e.get("date"),
            "state": state,
            "status": status_es(st, sport),
            "timeTbd": comp.get("timeValid") is False,
            "note": notes[0] if notes else None,
            "venue": (comp.get("venue") or {}).get("fullName"),
            "tv": bc or None,
            "link": link,
            "sides": sides,
            # Las líneas solo tienen sentido antes y durante el partido (son las de cierre previas).
            "odds": parse_odds(comp, sport) if state in ("pre", "in") else None,
        })
    return games


def days_urls(path, now):
    today = now.astimezone(CR).date()
    return [BASE + path + "/scoreboard?dates=" + (today + timedelta(days=d)).strftime("%Y%m%d") for d in (-1, 0, 1)]


def tennis_games(data, tour, now):
    lo, hi = now - timedelta(hours=TENNIS_WINDOW_H), now + timedelta(hours=TENNIS_WINDOW_H)
    out = []
    for e in (data or {}).get("events", []):
        for g in e.get("groupings", []):
            slug = (g.get("grouping") or {}).get("slug", "")
            if slug not in ("mens-singles", "womens-singles"):
                continue
            for c in g.get("competitions", []):
                try:
                    d = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                if not (lo <= d <= hi):
                    continue
                comps = c.get("competitors", [])
                names = [(x.get("athlete") or {}).get("displayName") for x in comps]
                if len(comps) != 2 or not all(names) or "TBD" in names:
                    continue
                st = c.get("status") or {}
                rnd = (c.get("round") or {}).get("displayName") or ""
                qual = "Qualif" in rnd
                sides = []
                for x in sorted(comps, key=lambda x: x.get("order", 0)):
                    a = x.get("athlete") or {}
                    sets = []
                    for l in x.get("linescores", []):
                        v = _num(l.get("value"))
                        if v is None:
                            continue
                        sets.append({"v": v, "tb": l.get("tiebreak")})
                    sides.append({"name": a.get("displayName"), "short": a.get("shortName"),
                                  "country": (a.get("flag") or {}).get("alt"), "flag": (a.get("flag") or {}).get("href"),
                                  "seed": x.get("seed") or None, "winner": x.get("winner"), "sets": sets})
                out.append({
                    "id": c.get("id"),
                    "start": c["date"],
                    "state": (st.get("type") or {}).get("state", "pre"),
                    "status": status_es(st, "tennis"),
                    "timeTbd": c.get("timeValid") is False,
                    "group": f"{e.get('name')} · {tour}",
                    "note": ("Clasificación" if qual else ROUNDS.get(rnd, rnd)) + " · " + ("Masculino" if slug.startswith("mens") else "Femenino"),
                    "qualifying": qual,
                    "link": None,
                    "sides": sides,
                })
    # Cuadro principal antes que la clasificación; en juego, luego terminados recientes, luego próximos.
    out.sort(key=lambda g: (g["qualifying"], {"in": 0, "post": 1, "pre": 2}.get(g["state"], 3)))
    main = [g for g in out if not g["qualifying"]]
    return (main if len(main) >= 6 else out)[:TENNIS_MAX]


def mma_games(data):
    out = []
    for e in (data or {}).get("events", []):
        comps = list(reversed(e.get("competitions", [])))   # ESPN pone la estelar al final
        for i, c in enumerate(comps):
            st = c.get("status") or {}
            sides = []
            for x in sorted(c.get("competitors", []), key=lambda x: x.get("order", 0)):
                a = x.get("athlete") or {}
                rec = next((r.get("summary") for r in x.get("records", []) if r.get("name") == "overall"), None)
                sides.append({"name": a.get("displayName") or "?", "short": a.get("shortName"),
                              "country": (a.get("flag") or {}).get("alt"), "flag": (a.get("flag") or {}).get("href"),
                              "record": rec, "winner": x.get("winner"),
                              "title": any(ac.get("type") == "Belt" for ac in a.get("accolades", []) or [])})
            if len(sides) != 2:
                continue
            wc = (c.get("type") or {}).get("abbreviation") or ""
            wc = WEIGHTS.get(wc, wc)
            state = (st.get("type") or {}).get("state", "pre")
            out.append({
                "id": c.get("id"), "start": c.get("date") or e.get("date"),
                "state": state,
                "status": status_es(st, "mma"),
                "group": e.get("name"),
                "note": ("Pelea estelar · " if i == 0 else "") + wc,
                "link": next((l.get("href") for l in e.get("links", []) if "summary" in (l.get("rel") or [])), None),
                "sides": sides,
                "odds": parse_odds(c, "mma") if state == "pre" else None,
            })
    return out


WEIGHTS = {"Heavyweight": "Peso pesado", "Light Heavyweight": "Peso semipesado", "Middleweight": "Peso mediano",
           "Welterweight": "Peso wélter", "Lightweight": "Peso ligero", "Featherweight": "Peso pluma",
           "Bantamweight": "Peso gallo", "Flyweight": "Peso mosca", "W Strawweight": "Peso paja femenino",
           "W Flyweight": "Peso mosca femenino", "W Bantamweight": "Peso gallo femenino",
           "W Featherweight": "Peso pluma femenino", "Catchweight": "Peso pactado"}


def build_league(lg, now):
    sport = (lg["path"] or "tennis/").split("/")[0]
    errs = []
    if lg["mode"] == "tennis":
        games = []
        for tour, label in (("atp", "ATP"), ("wta", "WTA")):
            data, err = fetch(BASE + "tennis/" + tour + "/scoreboard")
            if err:
                errs.append(f"{label}: {err}")
            games += tennis_games(data, label, now)
    elif lg["mode"] == "mma":
        data, err = fetch(BASE + lg["path"] + "/scoreboard")
        errs += [err] if err else []
        games = mma_games(data)
    elif lg["mode"] == "week":
        data, err = fetch(BASE + lg["path"] + "/scoreboard" + lg.get("query", ""))
        if err and lg.get("query"):  # si falla la lista completa, al menos el marcador por defecto
            data, err = fetch(BASE + lg["path"] + "/scoreboard")
        errs += [err] if err else []
        games = team_games(data, sport)
    else:
        games, seen = [], set()
        for url in days_urls(lg["path"], now):
            data, err = fetch(url)
            errs += [err] if err else []
            for g in team_games(data, sport):
                if g["id"] not in seen:
                    seen.add(g["id"])
                    games.append(g)
        if not games and not errs:  # fuera de temporada o día libre: próxima fecha con partidos
            data, err = fetch(BASE + lg["path"] + "/scoreboard")
            games = [g for g in team_games(data, sport) if g["state"] == "pre"]
    order = {"in": 0, "post": 1, "pre": 2}
    games.sort(key=lambda g: (order.get(g["state"], 3),
                              -_ts(g["start"]) if g["state"] == "post" else _ts(g["start"])))
    out = {k: lg[k] for k in ("id", "label", "name", "official", "officialName")}
    out.update({"path": lg["path"], "mode": lg["mode"], "games": games, "counts": {s: sum(1 for g in games if g["state"] == s) for s in ("in", "post", "pre")}})
    if errs and not games:
        out["error"] = "No se pudieron leer los marcadores en esta actualización."
    return out, (errs[0] if errs else "ok")


def _ts(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return 0


def build(now):
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda lg: build_league(lg, now), LEAGUES))
    leagues = [r[0] for r in results]
    report = {lg["id"]: (len(lg["games"]) if r == "ok" else r) for lg, (_, r) in zip(leagues, results)}
    if not any(lg["games"] for lg in leagues):
        return None, report
    # Pestaña por defecto: NFL si tiene partidos; si no, la liga con más partidos.
    default = "nfl" if leagues[0]["games"] else max(leagues, key=lambda lg: len(lg["games"]))["id"]
    return {
        "leagues": leagues,
        "default": default,
        "source": "ESPN",
        "sourceUrl": "https://www.espn.com/",
        "fetchedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "oddsCount": sum(1 for lg in leagues for g in lg["games"] if g.get("odds")),
    }, report


if __name__ == "__main__":
    data, rep = build(datetime.now(timezone.utc))
    print(rep)
    if data:
        for lg in data["leagues"]:
            print(lg["id"], lg["counts"], [(g["status"], [s.get("name") for s in g["sides"]], [s.get("score") for s in g["sides"]]) for g in lg["games"][:2]])
