# Noticias · briefing de consenso

Página móvil (en español) que muestra **solo las noticias que publican varios medios a la vez**. La idea es quitar el ruido: si una historia aparece en un solo medio, no se muestra. Si la publican 3, 5 o 19 medios distintos, aparece, ordenada por cuántos medios la cubren.

Pestañas, en este orden: Buenas noticias (la que abre), Costa Rica, Mundo de finanzas, Criptomonedas, Política, Ciencias, Mundo (con filtros por región), Sucesos, Guerras y conflictos y Posibles noticias.

**Abrir en el teléfono:** https://kbpsy505.github.io/noticias-app/ (en Chrome; no hace falta cuenta ni instalar nada).

## Cómo funciona (solo código, sin IA)

Cada 3 horas, GitHub Actions ejecuta `actualizar.py`:

1. **Recolectar.** Lee unos 90 canales RSS públicos en español e inglés (lista en `feeds.py`): BBC y BBC Mundo, El País, El Mundo, Expansión, The Economist, Financial Times, Bloomberg, Nature, Science, The Guardian, The New York Times, NPR, Al Jazeera, CBS News, Sky News, CNBC, DW, France 24, RFI, Euronews, Noticias ONU, Le Monde, El Confidencial, ABC, La Vanguardia, Europa Press, 20minutos, Infobae, Clarín, La Nación (Argentina), El Tiempo, El Comercio (Perú), La Nación y El Financiero (Costa Rica), El Mundo CR y Monumental. De cada nota guarda título, enlace, medio, idioma, hora y el resumen que trae el propio feed (sin HTML, máximo ~400 caracteres). Si un feed falla, se salta y queda anotado en `noticias.json`.
2. **Filtrar.** Descarta opinión, podcasts, videos, blogs en vivo, deportes, cultura y notas de más de 48 horas (7 días en ciencia).
3. **Normalizar.** Pasa títulos y resúmenes a un vocabulario común: quita tildes y palabras vacías, traduce términos frecuentes del español al inglés con un diccionario pequeño (`vocab.py`: países, gentilicios, “alto el fuego” → *ceasefire*, “aranceles” → *tariff*…) y recorta cada palabra a 6 letras para que “elecciones” y “elections” coincidan.
4. **Agrupar.** Compara cada par de notas con TF‑IDF (similitud de coseno). Dos notas se unen solo si: se publicaron con 36 horas o menos de diferencia, su similitud es alta, comparten al menos 2 términos poco comunes (nombres, lugares, cifras) y al menos uno está en ambos titulares. Al unir grupos se exige que la similitud promedio entre todas sus notas siga siendo alta, para no encadenar historias distintas.
5. **Consenso.** Se queda solo con los grupos que publican **3 o más medios distintos** (`MIN_OUTLETS` en `actualizar.py`; igual en todas las pestañas de consenso, incluida Criptomonedas). Ediciones del mismo grupo cuentan como un solo medio: BBC = BBC Mundo, El País = El País English, DW EN = DW ES, France 24 EN = ES, RFI EN = ES, Euronews EN = ES, El Mundo = Expansión, La Nación CR = El Financiero CR.
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

## Buenas noticias de Costa Rica y deportes

- **Costa Rica** (`cr_buenas.py`, `cr_filtro.py`): medios ticos (La Nación/La Teja, CRHoy, Teletica, Repretel, AmeliaRueda, Diario Extra, Delfino, Semanario Universidad, El Observador, Trivisión, El Mundo CR, AM Prensa, Monumental, Tico Times, The Costa Rica News), la UCR, el TEC y la UNA, más búsquedas de Google Noticias por sitio con palabras positivas (`when:7d` va al inicio de la búsqueda). Tiene su propio filtro en español tico: exige un ángulo tico (lugar, institución o gentilicio) y descarta sucesos, pleitos políticos, lotería, farándula, eventos y publicidad de empresas.
- Tienen su propio espacio: hasta 12 notas de Costa Rica, máximo 3 por medio, aparte del tope global de 60. En la página se filtran con los botones Todas / Costa Rica / Mundo.
- Titulares ticos cortos del mismo hecho se agrupan en una sola tarjeta: comparten palabras raras de la semana (por raíz: «cohete» = «cohetería») dentro de 72 h.
- **Deportes** (`deportes.py`): cuenta cualquier triunfo (títulos, medallas, récords, clasificaciones, premios, primeros lugares), no resultados de partidos, derrotas, fichajes, lesiones, apuestas, escándalos ni previas. Máximo 6 en Costa Rica y 6 en lo global, con la etiqueta «Deportes».
- Se descartan notas «positivas» débiles: guerra o tema militar, negaciones («aún no»), críticas o investigaciones, déficits y avances parciales de obras.

## Costa Rica y regiones de Mundo

`regiones.py` agrega Costa Rica, Centroamérica, Latinoamérica (México, Caribe y temas latinoamericanos generales), Sudamérica, Europa, Asia (incluye Medio Oriente), África y Australia y Oceanía.

- Suma medios locales de cada región (p. ej. en Costa Rica: La Nación/El Financiero/La Teja, CRHoy, Teletica/Telenoticias, Repretel, Diario Extra, Trivisión, El Observador, Delfino, Semanario Universidad, El Mundo CR, Monumental, AM Prensa, Q Costa Rica) a todas las notas de las pestañas de tema, y agrupa igual que el resto.
- Misma regla: **3 o más medios distintos** por historia.
- Medios ticos sin RSS: CRHoy y Trivisión se leen de su sitemap de noticias. Si el feed propio falla o no trae notas de las últimas 48 h (Teletica, Repretel), se usa Google Noticias limitado a su sitio (`site:`), con el nombre del medio original. La Gaceta (Imprenta Nacional) no tiene RSS ni sitemap de publicaciones, así que no se incluye.
- La región sale de los lugares, países y personajes que nombran los titulares y resúmenes. Para asignarla, al menos 2 medios distintos deben nombrar un lugar de esa región, y entre esos y los medios locales de la región deben sumar la mitad del grupo. Las historias que son sobre todo de EE. UU. no van a ninguna región. Una historia puede salir también en su pestaña de tema.
- Costa Rica tiene pestaña propia. Las demás regiones van dentro de **Mundo**, con filtros Todas / General / Centroamérica / Latinoamérica / Sudamérica / Europa / Asia / África / Oceanía y su número de historias. En «Todas», una historia que está en Mundo general y en una región (comparten notas) sale una sola vez con sus etiquetas de región, ordenadas por número de medios y luego por lo más reciente (`merge_mundo` en `actualizar.py`). La regla de 3+ medios no cambia.
- Informe en `noticias.json` → `regions` (feeds que fallaron, medios locales activos por región, grupos de 2 medios que no llegaron a 3).

## Pestaña "Posibles noticias"

Historias **sin confirmar** que publican **2 medios distintos** (no llegaron a los 3 de consenso). Salen de los mismos agrupamientos de las pestañas de tema, de región y de cripto. Cada tarjeta lleva etiquetas de categoría/región, el número de medios y las fuentes.

- Nada se repite con las pestañas de consenso: se descarta cualquier grupo que comparta una nota con una historia de 3+ medios. Los grupos repetidos entre corpus se fusionan.
- Orden: más medios primero y luego lo más reciente. Hay tope de 60 en total y 8 por categoría/región, y se reservan hasta 3 por cada una (6 para Criptomonedas) para que Costa Rica, Centroamérica o cripto no queden tapadas (`POSIBLES_*` en `actualizar.py`).
- Si todos los medios de un grupo son de la misma región, o la mitad lo son y la región se nombra, la historia va a esa región aunque el titular no diga el lugar.
- Informe en `noticias.json` → `possible`.

## Mundo de finanzas y Ciencias reforzadas

`tema.py` suma medios especializados a estas dos pestañas y agrupa aparte, con la misma regla de **3 o más medios distintos**.

- **Finanzas:** CNBC, WSJ, MarketWatch, Bloomberg, FT, Cinco Días, Bloomberg Línea, Axios, Fortune, Business Insider y, por Google Noticias por sitio (`when:2d`), Reuters, AP, WSJ, Barron's, Nikkei Asia, Yahoo Finanzas, El Economista, La República y El Financiero CR. Se descartan consejos de finanzas personales, ensayos en primera persona, «X acciones para comprar», charla de cotizaciones, resúmenes de media sesión y comunicados. Las notas de mercado que mencionan una guerra (p. ej. «el petróleo sube por Oriente Medio») salen en Finanzas y también en Guerras.
- **Ciencias:** Scientific American, Quanta, Ars Technica, Science News, Smithsonian, The Conversation, NYT Space, ScienceDaily, Phys.org, NASA, ESA, Muy Interesante y, por Google Noticias (`when:7d`), Reuters, AP, CNN, New Scientist, National Geographic, Live Science, Space.com, SINC e Infobae. Ventana de 7 días y agrupación más larga, porque la ciencia se publica en días distintos. Se descartan ofertas, guías del cielo y páginas de autor.
- **Medios que cuentan:** los que reescriben comunicados o son fuente primaria (ScienceDaily, Phys.org, NASA, ESA, Space.com, Live Science, Muy Interesante) y los de menor fiabilidad en negocios (Business Insider, Fortune, Barron's) solo suman cuando la historia ya tiene 2+ medios confiables. Yahoo Finanzas nunca cuenta. Todos se muestran como fuentes.
- Una segunda pasada une grupos del mismo hecho contado con palabras distintas (centros parecidos y términos o nombres propios poco comunes en común).
- Informe en `noticias.json` → `topics`.

## Pestaña "Criptomonedas"

`cripto.py` arma una pestaña con consenso estricto: una noticia de criptomonedas solo aparece si la publican **3 o más medios distintos** (misma regla de organizaciones que el resto).

- Fuentes: los feeds generales y financieros de la app más medios cripto y de negocios (CoinDesk, The Block, Decrypt, Cointelegraph, Bitcoin Magazine, The Defiant, Unchained, Protos, CryptoSlate, Crypto Briefing, CriptoNoticias, DiarioBitcoin, Bloomberg, FT, Expansión…). Reuters, Bloomberg, CNBC, WSJ, Fortune, Axios, Forbes, Yahoo Finanzas, Infobae, El Economista y Expansión entran también por búsquedas de Google Noticias por sitio (`when:2d` al inicio).
- **Medios que cuentan:** los de baja fiabilidad o mucho contenido de precio (U.Today, CoinGape, Cryptonews, BeInCrypto, NewsBTC, Forbes) solo suman cuando ya hay **2+ medios confiables** en la historia. Yahoo Finanzas e Investing.com **nunca** cuentan porque republican notas de otros medios. Todos se muestran como fuentes («+N fuentes extra que no cuentan»), y el titular y el resumen se toman de un medio que cuenta (`LOW_TIER`, `AGGREGATORS`, `TIER_MODE` en `cripto.py`).
- Una segunda pasada une grupos que cuentan el mismo hecho con palabras distintas (centros parecidos y 2+ términos poco comunes en los titulares de ambos, dentro de 48 h).
- Se descartan comunicados de prensa (PR Newswire, GlobeNewswire, Business Wire…), contenido patrocinado, predicciones de precio, análisis técnico (soportes, resistencias, «could surge», «altcoins a observar»), páginas de cotización, listas de "monedas para comprar" y airdrops.
- La agrupación usa el mismo código que las demás pestañas; la rareza de los términos se mide contra todo el corpus del día.
- Si ninguna noticia llega a 3 medios, la pestaña lo dice en vez de mostrar algo sin verificar. Informe en `noticias.json` → `crypto`.

## Tipo de cambio

`tipocambio.py` agrega al encabezado (visible en todas las pestañas) el tipo de cambio de referencia del BCCR, en cada actualización de 3 horas, y lo guarda en `noticias.json` → `exchange`.

- **Dólar y ventanilla:** [TipoCambioCR](https://www.tipocambiocr.net/) (API pública sin llave: `/today/full.json` y `/api/snapshots` para el cambio contra el día anterior). Muestra compra/venta, el cambio vs. el día anterior, la referencia de mañana cuando BCCR ya la publicó (`bccrPreview`, después de ~5:30 p. m.), la mejor compra/venta y una tabla plegable de bancos, cooperativas, mutuales, financieras, casas de cambio y puestos de bolsa. Se ocultan tasas a más de 10 % de la referencia.
- **Euro:** API del Ministerio de Hacienda (`api.hacienda.go.cr/indicadores/tc`), que también sirve de respaldo para el dólar si TipoCambioCR no responde.
- Crédito: «Datos: TipoCambioCR» bajo las cifras y el botón «Ver más en TipoCambioCR ↗».
- Si las dos fuentes fallan, el bloque no aparece y el resto de la actualización sigue igual.

## Precios de criptomonedas

`criptoprecios.py` agrega, en cada actualización de 3 horas, los precios de BTC, ETH, SOL, XRP, BNB, DOGE, ADA y USDT, y los guarda en `noticias.json` → `cryptoPrices` (informe en `cryptoPricesReport`). Es la primera sección de la pestaña Criptomonedas, antes de la nota y de las noticias.

- **Fuente:** [CoinGecko](https://www.coingecko.com/es), API pública sin llave (`/api/v3/coins/markets` con `sparkline=true`): una sola llamada por actualización, muy por debajo del límite gratuito. Hasta 3 intentos si responde 429/5xx.
- **App:** gráfica de 7 días (SVG, sin librerías) de la moneda elegida con precio, equivalente aproximado en colones (venta BCCR), cambio 24 h y 7 d, rango 24 h y capitalización; debajo, lista con mini gráfica, precio y cambio 24 h. Tocar una moneda cambia la gráfica. Verde sube, rojo baja.
- Los precios no son en tiempo real: se renuevan con cada actualización y la sección lo dice.
- Si CoinGecko falla, la sección no aparece y las noticias siguen igual.

## Tour de bienvenida

`tour.js` (sin librerías) muestra un tour corto de 6 pasos la primera vez que alguien abre la página: bienvenida, pestañas, etiqueta de medios, tarjeta, Posibles noticias y hora de actualización. Resalta cada parte real de la página y arranca cuando ya cargó `noticias.json`. Se marca como visto en `localStorage` (`noticias_tour_v1`) y se repite con el botón «?» del encabezado. Si falta un elemento (p. ej. una pestaña vacía), el mensaje se muestra centrado.
