# Noticias (prototipo)

Pantalla móvil para leer titulares reales en seis categorías: Sucesos, Política, Mundo de finanzas, Mundo, Ciencias y Guerras actuales. Cada tarjeta muestra el titular, el medio, la etiqueta ES o EN, la hora y un enlace al artículo original. No hay cuenta ni tienda de aplicaciones.

Los textos salen de RSS públicos. Si un feed falla o no trae actualidad, se omite. No se inventan titulares, citas ni enlaces.

## Cómo abrirlo en el teléfono

El navegador no puede leer el JSON si abres el archivo directo (`file://`). Hay que servir la carpeta.

1. En un ordenador de la misma red Wi‑Fi que el Android:

   ```bash
   cd /workspace/noticias-app
   python3 -m http.server 8080
   ```

2. Averigua la IP del ordenador (`ip addr` o la configuración de la red) y, en Chrome del teléfono, abre `http://ESA-IP:8080`.

3. La primera pantalla es `index.html`.

## Cada 3 horas

La página muestra la última descarga y la hora de la siguiente (hora de Costa Rica). Esos datos viven en `noticias.json`.

Para bajar titulares otra vez:

```bash
python3 actualizar.py
```

Puedes dejarlo en cron cada 3 horas. Si ya pasó la hora y nadie ejecutó el script, la pantalla lo dice y sigue mostrando la última tanda real. No rellena huecos con noticias inventadas.

## Fuentes que sí respondieron

BBC, BBC Mundo, El País (incluida la edición en inglés), El Mundo, The Economist, Financial Times, Bloomberg, Nature y Science.

## Fuentes que no se usaron

- Reuters: no hay RSS público de titulares (404 y 401).
- Associated Press: la web responde 403; no hay un RSS abierto utilizable.
- AFP: el RSS de afp.com no es un cable de noticias; solo notas viejas de la agencia (2012–2021).
- Wall Street Journal: el RSS gratuito responde, pero los ítems siguen en enero de 2025. No es un feed vivo.
- El Mundo sucesos: HTTP 404.

## Qué hay en la carpeta

- `index.html` — entrada
- `styles.css`, `app.js` — interfaz
- `noticias.json` — titulares de la última descarga
- `actualizar.py` — vuelve a pedir los RSS y reescribe el JSON
