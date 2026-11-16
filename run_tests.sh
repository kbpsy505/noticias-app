#!/usr/bin/env bash
# Pruebas de Noticias (sin red). Uso: ./run_tests.sh   (PY=/ruta/python para otro intérprete)
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-python3}"
echo "== pytest =="
"$PY" -m pytest tests -q
echo "== node --test =="
node --test tests/js/*.mjs
