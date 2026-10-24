"""Precios de criptomonedas para la pestaña Criptomonedas.

Fuente, sin llave ni registro: CoinGecko, API pública (https://www.coingecko.com/en/api).
Una sola llamada a /coins/markets con sparkline de 7 días por cada actualización (cada ~3 h),
muy por debajo del límite gratuito (~5–30 llamadas por minuto). Si falla, se devuelve None
y la app simplemente no muestra la sección; nunca rompe la actualización de noticias.
"""
from __future__ import annotations

import json
import time
import urllib.request

UA = "Mozilla/5.0 (compatible; noticias-app; +https://kbpsy505.github.io/noticias-app/)"
API = "https://api.coingecko.com/api/v3/coins/markets"
# Orden de la lista en la app: las más grandes y líquidas, más una estable de referencia.
COINS = ["bitcoin", "ethereum", "solana", "ripple", "binancecoin", "dogecoin", "cardano", "tether"]
SPARK_POINTS = 56   # 7 días de datos horarios (~168) reducidos a uno cada 3 h


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _shrink(values, n=SPARK_POINTS):
    vals = [v for v in values if isinstance(v, (int, float))]
    if len(vals) <= n:
        return vals
    step = (len(vals) - 1) / (n - 1)
    return [vals[round(i * step)] for i in range(n)]


def _sig(v):
    """Redondeo que conserva precisión en monedas baratas (DOGE, ADA)."""
    if v is None:
        return None
    if abs(v) >= 1000:
        return round(v, 0)
    if abs(v) >= 1:
        return round(v, 2)
    return round(v, 5)


def build(now):
    url = (API + "?vs_currency=usd&ids=" + ",".join(COINS)
           + "&sparkline=true&price_change_percentage=24h,7d&precision=full")
    rows, err = None, None
    for attempt in range(3):   # 429/5xx ocasionales: reintento corto
        try:
            rows = get(url)
            break
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            time.sleep(4 * (attempt + 1))
    if not rows:
        return None, {"coingecko": err or "vacío"}
    by_id = {r.get("id"): r for r in rows}
    coins = []
    for cid in COINS:
        r = by_id.get(cid)
        if not r or r.get("current_price") is None:
            continue
        spark = _shrink((r.get("sparkline_in_7d") or {}).get("price") or [])
        coins.append({
            "id": cid,
            "symbol": (r.get("symbol") or "").upper(),
            "name": r.get("name"),
            "price": _sig(r["current_price"]),
            "change24h": round(r["price_change_percentage_24h_in_currency"] if r.get("price_change_percentage_24h_in_currency") is not None
                               else (r.get("price_change_percentage_24h") or 0), 2),
            "change7d": None if r.get("price_change_percentage_7d_in_currency") is None
                        else round(r["price_change_percentage_7d_in_currency"], 2),
            "high24h": _sig(r.get("high_24h")),
            "low24h": _sig(r.get("low_24h")),
            "marketCap": r.get("market_cap"),
            "rank": r.get("market_cap_rank"),
            "spark7d": [_sig(v) for v in spark],
            "url": "https://www.coingecko.com/es/monedas/" + cid,
        })
    if not coins:
        return None, {"coingecko": "sin monedas"}
    out = {
        "currency": "USD",
        "coins": coins,
        "source": "CoinGecko",
        "sourceUrl": "https://www.coingecko.com/es",
        "updatedAt": max((r.get("last_updated") or "" for r in rows), default="") or now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetchedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return out, {"coingecko": "ok", "monedas": len(coins)}


if __name__ == "__main__":
    from datetime import datetime, timezone
    data, rep = build(datetime.now(timezone.utc))
    print(rep)
    print(json.dumps(data, ensure_ascii=False)[:800])
