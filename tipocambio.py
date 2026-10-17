"""Tipo de cambio dólar/colón (y euro) para el encabezado.

Fuentes, sin llave ni registro:
- TipoCambioCR (https://www.tipocambiocr.net/developers): referencia BCCR compra/venta,
  ventanilla de bancos, cooperativas y casas de cambio, e historial diario.
- Ministerio de Hacienda (api.hacienda.go.cr/indicadores/tc): euro en colones y respaldo del dólar.
Las cifras salen tal cual de esas fuentes; si una falla, se usa la otra o se omite el bloque.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (compatible; noticias-app; +https://kbpsy505.github.io/noticias-app/)"
TCR = "https://www.tipocambiocr.net"
HACIENDA = "https://api.hacienda.go.cr/indicadores/tc"
CR = timezone(timedelta(hours=-6))
# Tasas de ventanilla a más de 10 % de la referencia (p. ej. casas con ₡364/₡544) se ocultan:
# suelen ser tasas de efectivo especial y confunden la comparación.
OUTLIER = 0.10
GROUPS = [("bancos-publicos", "Bancos públicos"), ("bancos-privados", "Bancos privados"),
          ("cooperativas", "Cooperativas"), ("mutuales-de-vivienda", "Mutuales"),
          ("financieras", "Financieras"), ("casas-de-cambio", "Casas de cambio"),
          ("puestos-de-bolsa", "Puestos de bolsa")]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def build(now):
    out, report = {"pair": "USD/CRC"}, {}
    try:
        full = get(TCR + "/today/full.json")
        b = full["bccr"]
        out["dolar"] = {"compra": b["compra"], "venta": b["venta"], "fecha": full["date"],
                        "fuente": "Banco Central de Costa Rica (vía TipoCambioCR)", "fuenteUrl": TCR + "/"}
        ref = b["venta"]
        rows = [r for r in full["rows"] if r["tipoEntidad"] != "bccr"]
        shown = [r for r in rows if abs(r["venta"] - ref) / ref <= OUTLIER and abs(r["compra"] - ref) / ref <= OUTLIER]
        out["ventanilla"] = [
            {"id": g, "label": label, "rows": sorted(
                ({"entidad": r["entidad"], "compra": r["compra"], "venta": r["venta"]} for r in shown if r["tipoEntidad"] == g),
                key=lambda r: r["venta"])}
            for g, label in GROUPS if any(r["tipoEntidad"] == g for r in shown)]
        if shown:
            bv = min(shown, key=lambda r: r["venta"])
            bc = max(shown, key=lambda r: r["compra"])
            out["mejorVenta"] = {"entidad": bv["entidad"], "venta": bv["venta"]}
            out["mejorCompra"] = {"entidad": bc["entidad"], "compra": bc["compra"]}
        out["ventanillaCapturada"] = full.get("capturedAt")
        # Referencia del próximo día hábil (BCCR la publica ~5:30 p. m.; TipoCambioCR la guarda como bccrPreview).
        pv = full.get("bccrPreview") or {}
        pdate = pv.get("date") or pv.get("fecha") or pv.get("effectiveDate")
        if pv.get("venta") and pdate and pdate > full["date"]:
            out["manana"] = {"fecha": pdate, "compra": pv.get("compra"), "venta": pv["venta"]}
        report.update(tipocambiocr="ok", entidades=len(rows), ocultas=len(rows) - len(shown))
        # Cambio contra el día anterior con dato (historial de TipoCambioCR).
        since = (now.astimezone(CR) - timedelta(days=10)).strftime("%Y-%m-%d")
        snaps = [s for s in get(TCR + "/api/snapshots?from=" + since)["snapshots"] if s["date"] < full["date"]]
        if snaps:
            prev = max(snaps, key=lambda s: s["date"])
            out["dolar"]["anterior"] = {"fecha": prev["date"], "compra": prev["bccr_compra"], "venta": prev["bccr_venta"]}
            out["dolar"]["cambioVenta"] = round(b["venta"] - prev["bccr_venta"], 2)
            out["dolar"]["cambioCompra"] = round(b["compra"] - prev["bccr_compra"], 2)
    except Exception as exc:  # noqa: BLE001
        report["tipocambiocr"] = f"{type(exc).__name__}: {exc}"
    try:
        h = get(HACIENDA)
        e = h["euro"]
        out["euro"] = {"colones": e["colones"], "dolares": e["dolares"], "fecha": e["fecha"],
                       "fuente": "Ministerio de Hacienda", "fuenteUrl": "https://api.hacienda.go.cr/indicadores/tc/euro"}
        if "dolar" not in out:   # respaldo si TipoCambioCR no responde
            d = h["dolar"]
            out["dolar"] = {"compra": d["compra"]["valor"], "venta": d["venta"]["valor"], "fecha": d["venta"]["fecha"],
                            "fuente": "Banco Central de Costa Rica (vía Hacienda)", "fuenteUrl": HACIENDA}
        report["hacienda"] = "ok"
    except Exception as exc:  # noqa: BLE001
        report["hacienda"] = f"{type(exc).__name__}: {exc}"
    out["consultado"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (out if "dolar" in out else None), report


if __name__ == "__main__":
    data, rep = build(datetime.now(timezone.utc))
    print(json.dumps(rep, ensure_ascii=False))
    print(json.dumps(data, ensure_ascii=False, indent=1)[:2500])
