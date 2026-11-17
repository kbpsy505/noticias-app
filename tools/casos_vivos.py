#!/usr/bin/env python3
"""Revisa los casos fijos sobre una salida real (noticias.json de una corrida en vivo). Solo lectura."""
import json
import sys


def headline(s):
    return (s.get("headline", "") + " " + (s.get("headlineEn") or "")).lower()


def check(path):
    d = json.load(open(path, encoding="utf-8"))
    cards = [(c["id"], s) for c in d["categories"] if c["id"] != "posibles" for s in c["stories"]]
    out = []
    q = [(cid, s) for cid, s in cards if "quepos" in headline(s) and ("oxford" in headline(s) or "beca" in headline(s))]
    if not q:
        out.append(("Quepos/Oxford", "SIN DATO", "la historia no está en esta corrida"))
    else:
        cid, s = q[0]
        ok = (len(q) == 1 and (s.get("section") or cid) == "costarica"
              and any(a.get("section") == "avances" or a.get("id") == "buenas" for a in s.get("alsoIn", []))
              and "news.google.com" not in s["sources"][0]["url"])
        out.append(("Quepos/Oxford", "OK" if ok else "FALLA",
                    f"{len(q)} tarjeta(s); sección {s.get('section') or cid}; alsoIn {[a.get('label') for a in s.get('alsoIn', [])]}; "
                    f"enlace {s['sources'][0]['url'][:80]}"))
    for name, word in (("Carney", "carney"), ("Camilo Rodríguez (asesinato)", "asesinan al periodista camilo")):
        hits = [(cid, s) for cid, s in cards if word in headline(s)]
        dup = len(hits) - 1 if hits else 0
        out.append((name, "SIN DATO" if not hits else ("OK" if dup == 0 else "FALLA"),
                    f"{len(hits)} tarjeta(s), {dup} copia(s): {[cid for cid, _ in hits]}"))
    gn_first = sum(1 for _, s in cards if "news.google.com" in s["sources"][0]["url"])
    out.append(("Tarjetas con enlace principal de Google Noticias", "OK" if gn_first <= max(1, len(cards) // 50) else "FALLA",
                f"{gn_first} de {len(cards)}"))
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print("##", p)
        for row in check(p):
            print(" | ".join(row))
