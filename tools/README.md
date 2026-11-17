# Herramientas de prueba local (no corren en GitHub Actions)

- `feedcache.py` + `correr.py`: graban y reproducen las descargas para comparar main y la rama con la misma entrada.
  `NOTICIAS_FEED_CACHE=/ruta NOTICIAS_FEED_MODE=record|replay|replay+record python tools/correr.py --repo CLON --out salida.json --prev anterior.json`
  La caché (respuestas crudas) vive fuera del repo; aquí solo queda el inventario `tests/fixtures/feeds-grabados-2026-11-17.json`.
- `metricas.py`: tabla antes/después (tarjetas, historias únicas, duplicados, secciones, frescura, feeds, filtro tico).
- `casos_vivos.py`: revisa los casos fijos (Quepos, Carney, Camilo Rodríguez, enlaces de Google Noticias) sobre una salida real.
- Las llamadas a APIs de IA nunca se graban.
