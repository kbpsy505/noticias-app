# Noticias · briefing de consenso

Página móvil (en español) que muestra **solo las noticias que publican varios medios a la vez**. La idea es quitar el ruido: si una historia aparece en un solo medio, no se muestra. Si la publican 2, 5 o 19 medios distintos, aparece, ordenada por cuántos medios la cubren.

Categorías: Sucesos, Política, Mundo de finanzas, Mundo, Ciencias y Guerras actuales.

**Abrir en el teléfono:** https://kbpsy505.github.io/noticias-app/ (en Chrome; no hace falta cuenta ni instalar nada).

## Cómo funciona (solo código, sin IA)

Cada 3 horas, GitHub Actions ejecuta `actualizar.py`:

1. **Recolectar.** Lee unos 90 canales RSS públicos en español e inglés (lista en `feeds.py`): BBC y BBC Mundo, El País, El Mundo, Expansión, The Economist, Financial Times, Bloomberg, Nature, Science, The Guardian, The New York Times, NPR, Al Jazeera, CBS News, Sky News, CNBC, DW, France 24, RFI, Euronews, Noticias ONU, Le Monde, El Confidencial, ABC, La Vanguardia, Europa Press, 20minutos, Infobae, Clarín, La Nación (Argentina), El Tiempo, El Comercio (Perú), La Nación y El Financiero (Costa Rica), El Mundo CR y Monumental. De cada nota guarda título, enlace, medio, idioma, hora y el resumen que trae el propio feed (sin HTML, máximo ~400 caracteres). Si un feed falla, se salta y queda anotado en `noticias.json`.
2. **Filtrar.** Descarta opinión, podcasts, videos, blogs en vivo, deportes, cultura y notas de más de 48 horas (7 días en ciencia).
3. **Normalizar.** Pasa títulos y resúmenes a un vocabulario común: quita tildes y palabras vacías, traduce términos frecuentes del español al inglés con un diccionario pequeño (`vocab.py`: países, gentilicios, “alto el fuego” → *ceasefire*, “aranceles” → *tariff*…) y recorta cada palabra a 6 letras para que “elecciones” y “elections” coincidan.
4. **Agrupar.** Compara cada par de notas con TF‑IDF (similitud de coseno). Dos notas se unen solo si: se publicaron con 36 horas o menos de diferencia, su similitud es alta, comparten al menos 2 términos poco comunes (nombres, lugares, cifras) y al menos uno está en ambos titulares. Al unir grupos se exige que la similitud promedio entre todas sus notas siga siendo alta, para no encadenar historias distintas.
5. **Consenso.** Se queda solo con los grupos que publican **2 o más medios distintos**. Ediciones del mismo grupo cuentan como un solo medio: BBC = BBC Mundo, El País = El País English, DW EN = DW ES, France 24 EN = ES, RFI EN = ES, Euronews EN = ES, El Mundo = Expansión, La Nación CR = El Financiero CR.
6. **Ordenar y publicar.** Ordena por número de medios y luego por lo más reciente. Para cada historia guarda un titular en español (y en inglés si existe), el mejor resumen por idioma, el número de medios, la lista de fuentes con enlaces y la primera y última hora vista. Todo va a `noticias.json`, que la página lee.

Nada se inventa: los titulares y resúmenes son los que publica cada medio. La página enlaza siempre al original.

## Actualización automática

`.github/workflows/actualizar.yml` corre cada 3 horas (`0 */3 * * *`, en UTC) y también a mano desde la pestaña *Actions* (“Run workflow”). Si `noticias.json` cambió, lo guarda en `main` y GitHub Pages vuelve a publicar la página. GitHub a veces retrasa los cron unos minutos.

Para correrlo en tu computadora:

```bash
python3 actualizar.py           # escribe noticias.json
python3 actualizar.py --debug   # además escribe debug_clusters.txt para revisar los grupos
python3 -m http.server 8080     # y abre http://localhost:8080
```

Solo usa la biblioteca estándar de Python (3.10 o más reciente).

## Fuentes que no se pudieron usar

Reuters y AP (sin RSS público), Washington Post (502), CNN en Español (404), EFE (500 o XML inválido), The Independent (XML inválido), WSJ (feed congelado en 2025), CRHoy y Teletica (sin RSS válido). New Scientist a veces responde 406 y se salta.

## Limitaciones

- La agrupación es estadística: a veces deja separadas notas del mismo hecho (sobre todo entre idiomas) y, rara vez, une dos notas parecidas que no son el mismo hecho. `--debug` sirve para revisarlo.
- La categoría sale de reglas simples (sección del feed y palabras clave) y no siempre acierta.
- Muchos medios en español reproducen cables de agencias (EFE, Europa Press), así que dos medios pueden estar contando la misma fuente original.
- FT, Bloomberg y The Economist tienen muro de pago: el resumen del feed es corto.

## Próximo paso (todavía no)

Agregar un resumen escrito por IA para cada historia de consenso, que explique en qué coinciden los medios y en qué difieren. Se hará con una clave de xAI guardada como secreto de GitHub llamado `XAI_API_KEY`; la clave nunca irá en el código. Por ahora no se usa ninguna IA ni clave.

## Archivos

- `index.html`, `styles.css`, `app.js`: la página.
- `noticias.json`: el resultado de la última actualización.
- `actualizar.py`: descarga, agrupa y escribe el JSON.
- `feeds.py`: lista de feeds y medios.
- `vocab.py`: diccionario español–inglés y palabras vacías.
- `.github/workflows/actualizar.yml`: la tarea automática cada 3 horas.

## Pestaña "Buenas noticias"

`buenas.py` arma una pestaña aparte con progreso humano y buenas acciones (salud, ciencia y tecnología, medio ambiente, progreso social, buenas acciones, comunidad):

- Aquí basta **una** fuente confiable (secciones de soluciones y buenas noticias, ciencia, ONU, más las notas positivas de los feeds generales).
- Filtro solo con código: palabras de progreso (ES/EN) y de impacto medible; se descartan las notas negativas, amarillistas, de relleno (famosos, marcas, momentos virales sin impacto), de opinión y las listas.
- Reddit (r/UpliftingNews, r/science, etc.) y 9gag solo sirven como pistas: una pista entra únicamente si enlaza a un medio confiable, y lo que se muestra es ese medio.
- Máximo 40 notas, 5 por medio y 10 por subtema (12 en medio ambiente). El informe completo (feeds, pistas confirmadas y descartadas) queda en `noticias.json` → `goodNews`.
