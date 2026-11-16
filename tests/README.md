# Pruebas de Noticias

Sin red: los feeds se inyectan con fixtures locales. Se corren en el workflow antes de generar `noticias.json`.

```bash
./run_tests.sh              # pytest + node --test
python -m pytest tests -v   # solo Python
node --test tests/js/*.mjs  # solo JS
```

`test_source_risks.py` son regresiones de los riesgos corregidos el 2026-11-16 (antes xfail).
