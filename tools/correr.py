#!/usr/bin/env python3
"""Corre actualizar.py de un clon (main o la rama) con la caché de feeds y copia la salida.

Uso: NOTICIAS_FEED_CACHE=/ruta python tools/correr.py --repo /ruta/clon --out /ruta/salida.json [--prev prev.json]
- --prev: noticias.json «anterior» para la frescura (Nuevo/Sigue); se copia al clon antes de correr.
- Nunca hace commit ni push; deja el noticias.json del clon como estaba (git checkout) al terminar.
"""
import argparse
import os
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import feedcache  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--prev")
ap.add_argument("--debug", action="store_true")
a = ap.parse_args()

repo = Path(a.repo).resolve()
if a.prev:
    shutil.copy(a.prev, repo / "noticias.json")
os.chdir(repo)
sys.path.insert(0, str(repo))
feedcache.install()
sys.argv = [str(repo / "actualizar.py")] + (["--debug"] if a.debug else [])
t0 = time.time()
try:
    runpy.run_path(str(repo / "actualizar.py"), run_name="__main__")
finally:
    dur = time.time() - t0
    print(f"\n[correr] duración {dur:.0f} s · caché {feedcache.STATS}", file=sys.stderr)
    if (repo / "noticias.json").exists():
        shutil.copy(repo / "noticias.json", a.out)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--", "noticias.json"])
    for extra in ("narraciones.json",):
        p = repo / extra
        r = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", extra], capture_output=True)
        if r.returncode == 0:
            subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--", extra])
Path(a.out).with_suffix(".dur").write_text(f"{dur:.1f}\n")
