"""Pestaña "Buenas noticias": progreso humano y buenas acciones, solo con código.

Reglas:
- Basta UNA fuente confiable (no se exige consenso de 2+ medios).
- Fuentes: secciones de soluciones / buenas noticias de medios serios, cuerpos
  científicos y agencias de la ONU, más las notas positivas que aparezcan en los
  feeds generales del resto de la app.
- Reddit (y 9gag) solo sirven como pistas: una pista entra únicamente si enlaza o
  coincide con una nota de un medio confiable, y lo que se muestra es ese medio.
- Filtro "bueno" vs "amarillista": listas de palabras de progreso (ES/EN) y de
  exclusión (violencia, desastres, escándalo, clickbait, chismes...).
No inventa nada: titulares y resúmenes salen tal cual de cada medio.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import ssl
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urlparse

import actualizar as A

GOOD_HOURS = 24 * 7       # las secciones de soluciones publican despacio
GENERAL_HOURS = 72        # notas de los feeds generales
MAX_ITEMS = 40
PER_SUBTOPIC_MAX = 10
SUBTOPIC_MAX = {"ambiente": 12}
PER_OUTLET_MAX = 5
REDDIT_UA = "noticias-app/0.1 (personal news briefing; github.com/kbpsy505/noticias-app)"

SUBTOPICS = [
    ("salud", "Salud y medicina"),
    ("ciencia", "Ciencia y tecnología"),
    ("ambiente", "Medio ambiente"),
    ("social", "Progreso social"),
    ("acciones", "Buenas acciones"),
    ("comunidad", "Comunidad"),
]
SUB_LABEL = dict(SUBTOPICS)

# kind: "good" = sección dedicada a buenas noticias/soluciones (umbral bajo)
#       "topic" = sección temática seria (salud, ciencia, ambiente, ONU) (umbral medio)
# (id, url, medio, organización, idioma, kind, subtema por defecto)
GOOD_FEEDS = [
    ("pos-positivenews", "https://www.positive.news/feed/", "Positive News", "positivenews", "en", "good", "social"),
    ("pos-rtbc", "https://reasonstobecheerful.world/feed/", "Reasons to be Cheerful", "rtbc", "en", "good", "social"),
    ("pos-gnn", "https://www.goodnewsnetwork.org/feed/", "Good News Network", "gnn", "en", "good", "acciones"),
    ("pos-goodgoodgood", "https://www.goodgoodgood.co/articles/rss.xml", "Good Good Good", "goodgoodgood", "en", "good", "acciones"),
    ("pos-anthropocene", "https://www.anthropocenemagazine.org/feed/", "Anthropocene Magazine", "anthropocene", "en", "good", "ambiente"),
    ("pos-owid", "https://ourworldindata.org/atom.xml", "Our World in Data", "owid", "en", "topic", "social"),
    ("pos-guardian-dev", "https://www.theguardian.com/global-development/rss", "The Guardian", "guardian", "en", "topic", "social"),
    ("pos-guardian-wildlife", "https://www.theguardian.com/environment/wildlife/rss", "The Guardian", "guardian", "en", "topic", "ambiente"),
    ("pos-guardian-conserv", "https://www.theguardian.com/environment/conservation/rss", "The Guardian", "guardian", "en", "topic", "ambiente"),
    ("pos-guardian-medres", "https://www.theguardian.com/science/medical-research/rss", "The Guardian", "guardian", "en", "topic", "salud"),
    ("pos-guardian-renew", "https://www.theguardian.com/environment/renewableenergy/rss", "The Guardian", "guardian", "en", "topic", "ambiente"),
    ("pos-bbc-health", "https://feeds.bbci.co.uk/news/health/rss.xml", "BBC", "bbc", "en", "topic", "salud"),
    ("pos-bbc-tech", "https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC", "bbc", "en", "topic", "ciencia"),
    ("pos-nasa", "https://www.nasa.gov/news-release/feed/", "NASA", "nasa", "en", "topic", "ciencia"),
    ("pos-esa", "https://www.esa.int/rssfeed/Our_Activities/Space_Science", "ESA", "esa", "en", "topic", "ciencia"),
    ("pos-nih", "https://www.nih.gov/news-releases/feed.xml", "NIH", "nih", "en", "topic", "salud"),
    ("pos-un-health", "https://news.un.org/feed/subscribe/en/news/topic/health/feed/rss.xml", "UN News", "un", "en", "topic", "salud"),
    ("pos-un-climate", "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml", "UN News", "un", "en", "topic", "ambiente"),
    ("pos-un-sdg", "https://news.un.org/feed/subscribe/en/news/topic/sdgs/feed/rss.xml", "UN News", "un", "en", "topic", "social"),
    ("pos-onu-salud", "https://news.un.org/feed/subscribe/es/news/topic/health/feed/rss.xml", "Noticias ONU", "un", "es", "topic", "salud"),
    ("pos-onu-clima", "https://news.un.org/feed/subscribe/es/news/topic/climate-change/feed/rss.xml", "Noticias ONU", "un", "es", "topic", "ambiente"),
    ("pos-sciencedaily", "https://www.sciencedaily.com/rss/top/science.xml", "ScienceDaily", "sciencedaily", "en", "topic", "ciencia"),
    ("pos-sciencedaily-health", "https://www.sciencedaily.com/rss/top/health.xml", "ScienceDaily", "sciencedaily", "en", "topic", "salud"),
    ("pos-sciencedaily-env", "https://www.sciencedaily.com/rss/top/environment.xml", "ScienceDaily", "sciencedaily", "en", "topic", "ambiente"),
    ("pos-sciencedaily-tech", "https://www.sciencedaily.com/rss/top/technology.xml", "ScienceDaily", "sciencedaily", "en", "topic", "ciencia"),
    ("pos-mongabay", "https://news.mongabay.com/feed/", "Mongabay", "mongabay", "en", "topic", "ambiente"),
    ("pos-mongabay-es", "https://es.mongabay.com/feed/", "Mongabay Latam", "mongabay", "es", "topic", "ambiente"),
    ("pos-e360", "https://e360.yale.edu/feed.xml", "Yale Environment 360", "e360", "en", "topic", "ambiente"),
    ("pos-canary", "https://www.canarymedia.com/rss.rss", "Canary Media", "canary", "en", "topic", "ambiente"),
    ("pos-smithsonian", "https://www.smithsonianmag.com/rss/innovation/", "Smithsonian", "smithsonian", "en", "topic", "ciencia"),
    ("pos-conversation-en", "https://theconversation.com/global/articles.atom", "The Conversation", "conversation", "en", "topic", "ciencia"),
    ("pos-conversation-es", "https://theconversation.com/es/articles.atom", "The Conversation España", "conversation", "es", "topic", "ciencia"),
    ("pos-planetafuturo", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/planeta-futuro/portada", "El País", "elpais", "es", "topic", "social"),
    ("pos-elpais-clima", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/clima-y-medio-ambiente/portada", "El País", "elpais", "es", "topic", "ambiente"),
    ("pos-elpais-tec", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/tecnologia/portada", "El País", "elpais", "es", "topic", "ciencia"),
    ("pos-infobae-salud", "https://www.infobae.com/arc/outboundfeeds/rss/category/salud/", "Infobae", "infobae", "es", "topic", "salud"),
]

# Probados a mano y descartados (se listan en el JSON).
GOOD_KNOWN_FAILS = [
    ("guardian-the-upside", "https://www.theguardian.com/world/series/the-upside/rss", "Serie 'The upside' sin publicaciones desde 2024"),
    ("fixthenews", "https://fixthenews.substack.com/feed", "Fix the News solo publica boletines-resumen semanales (sin notas individuales)"),
    ("futurecrunch", "https://futurecrunch.com/feed/", "404 (ahora es Fix the News)"),
    ("who", "https://www.who.int/rss-feeds/news-english.xml", "Feed de la OMS congelado (última nota feb. 2026)"),
    ("npr-goodnews", "https://feeds.npr.org/1095/rss.xml", "Sin publicaciones desde 2024"),
    ("cbs-goodnews", "https://www.cbsnews.com/latest/rss/goodnews", "Feed vacío"),
    ("bbc-mundo-ciencia", "https://www.bbc.com/mundo/temas/ciencia/index.xml", "Congelado en 2014"),
    ("dw-sci", "https://rss.dw.com/rdf/rss-en-sci", "XML inválido"),
    ("dw-es-ciencia", "https://rss.dw.com/xml/rss-sp-cien", "XML inválido"),
    ("nature-news", "https://www.nature.com/nature/articles?type=news&format=rss", "XML inválido"),
    ("elpais-salud", "https://feeds.elpais.com/.../sociedad/salud/portada", "404"),
    ("unicef / unep / gavi", "-", "Sin RSS público (404)"),
    ("yes-magazine", "https://www.yesmagazine.org/feed", "Funciona pero sin notas recientes (sep. 2026)"),
]

REDDIT_SUBS = ["UpliftingNews", "HumansBeingBros", "science", "worldnews", "Futurology", "MadeMeSmile"]
NINEGAG_URL = "https://9gag.com/v1/interest-posts/interest/news/type/hot"

# Dominios de medios confiables para aceptar enlaces de Reddit (además de los feeds).
EXTRA_TRUSTED = {
    "apnews.com", "reuters.com", "washingtonpost.com", "cnn.com", "nbcnews.com", "abcnews.go.com",
    "cbsnews.com", "pbs.org", "npr.org", "usatoday.com", "latimes.com", "theatlantic.com", "time.com",
    "axios.com", "politico.com", "politico.eu", "abc.net.au", "cbc.ca", "theglobeandmail.com",
    "independent.co.uk", "telegraph.co.uk", "thetimes.co.uk", "irishtimes.com", "rte.ie",
    "scientificamerican.com", "nationalgeographic.com", "statnews.com", "nature.com", "science.org",
    "newscientist.com", "smithsonianmag.com", "eurekalert.org", "cdc.gov", "nih.gov", "who.int",
    "un.org", "unicef.org", "unep.org", "nasa.gov", "esa.int", "wired.com", "arstechnica.com",
    "technologyreview.com", "economist.com", "ft.com", "bloomberg.com", "nytimes.com", "theguardian.com",
    "bbc.com", "bbc.co.uk", "dw.com", "france24.com", "aljazeera.com", "euronews.com", "elpais.com",
    "elmundo.es", "infobae.com", "lanacion.com.ar", "nacion.com", "courthousenews.com", "sfgate.com",
    "coloradosun.com", "japantimes.co.jp", "scmp.com", "thehindu.com", "smh.com.au", "nzherald.co.nz",
    "rnz.co.nz", "sky.com", "thetimes.com", "globalnews.ca", "ctvnews.ca", "straitstimes.com",
    "asia.nikkei.com", "wpln.org", "pv-magazine.com", "astronomy.com", "timesofindia.indiatimes.com", "lemonde.fr", "spiegel.de", "nature.org", "worldwildlife.org", "theconversation.com",
}

PRETTY = {"abc.net.au": "ABC News (Australia)", "apnews.com": "AP News", "reuters.com": "Reuters",
          "bbc.co.uk": "BBC", "bbc.com": "BBC", "cbc.ca": "CBC", "manchester.ac.uk": "University of Manchester", "nytimes.com": "The New York Times"}

# ---------------------------------------------------------------- filtros de tono
NEG_TITLE = re.compile(
    r"(\bkill|\bdies\b|\bdied\b|\bdeath|\bdead(ly)?\b|murder|\bwar\b|\bwars\b|warfare|attack|\bbomb|shooting|gunman|"
    r"terror|scandal|shock|you won.?t believe|celebrit|kardashian|royal family|\bcrime|criminal|arrest|"
    r"disaster|catastroph|crisis|collapse|fraud|lawsuit|\bsue[ds]?\b|\bfear|threat|warn|decline|worst|slump|"
    r"\bcrash|layoff|\bcuts?\b|toxic|outbreak|abuse|\brape|victim|hostage|airstrike|\bfails?\b|failure|"
    r"fatal|tragic|tragedy|injur|alarming|troubling|dangerous|\brisk|grim|devastat|destroy|\bloss\b|losing|"
    r"\blost\b|extinct(?!ion)|poison|pollut(?!ion[- ]free)|starv|famine|refugee camp|conflict|violence|"
    r"\bhate\b|racis|protest|riot|trump|putin|netanyahu|\bmaga\b|sanction|tariff|smuggl|trafficking|"
    r"\bcheat|\bpanic|horror|nightmare|scam|epstein|\bsex\b|porn|\bnude|\bgun\b|guns\b|weapon|"
    r"\bmuer|mata\b|matan\b|asesin|guerra|ataque|bomba|tiroteo|terroris|esc[aá]ndalo|impactante|"
    r"no creer[aá]s|famos[oa]s|crimen|criminal|detenid|desastre|cat[aá]strofe|crisis|colapso|fraude|"
    r"demanda judicial|\bmiedo|amenaza|alerta|advierte|peor\b|ca[ií]da|despidos|recortes|t[oó]xic|"
    r"\bbrote|abuso|violaci[oó]n|v[ií]ctima|reh[eé]n|fracas|mortal|tragedia|herid|alarmante|preocupa|"
    r"pol[eé]mica|acusad|condena|p[eé]rdida|destru|contamina|hambruna|conflicto|violencia|odio|racism|"
    r"protesta|disturbio|sanci[oó]n|arancel|estafa|narco|\barma|peligr|riesgo|amenazad|extinci[oó]n de|"
    r"midterm|voter turnout|wake-up call|llamada de atenci[oó]n|rise in poverty|controvers|\bdenies\b|\bniega|backfire|sickness|harmful|zombie|super pac|lobby|\bspends?\b|\bdanger\b|worr(y|ied)|concern|el ni[nñ]o|la ni[nñ]a|s[uú]per ni[nñ]o|f[uú]tbol|futbolista|selecci[oó]n nacional|fichaj|tiktok|influencer|youtuber|barbie|\bkfc\b|coca-cola|mcdonald|starbucks|black friday|iphone|\bipo\b|stocks?\b|earnings|\bpapa\b|\bpope\b|desaparec|incendio|inundaci|sequ[ií]a|drought|wildfire|flood|heatwave|ola de calor)",
    re.I,
)
# En el resumen solo se excluye lo muy grave (el contexto negativo es normal en notas de soluciones).
NEG_SUMMARY = re.compile(
    r"(\bkilled\b|murder|massacre|\bwar crimes?\b|airstrike|genocide|\brape\b|asesinad|masacre|genocidio|"
    r"bombarde|crimen de guerra|celebrity|gossip|chisme|you won.?t believe)",
    re.I,
)
# Formatos que no son una nota: listas, resúmenes semanales, galerías, opinión, efemérides, ofertas.
FORMAT_SKIP = re.compile(
    r"(good news in history|what went right this week|the week in|this week in|weekly roundup|round-?up|"
    r"^\d+\s+(best|ways|things|reasons|tips|books|photos)|\b(top|best) \d+\b|^\d+:|photographer of the year|"
    r"in pictures|gift guide|\bdeals?\b|discount|sponsored|giveaway|quiz|horoscope|apod:|opinion|"
    r"\bpodcast|\bwebinar|newsletter|letters?:|^watch|^video|en im[aá]genes|lo mejor de la semana|"
    r"^in (19|20)\d\d\b|^en (19|20)\d\d\b|heaviest|tallest|\bbiggest\b|world record|r[eé]cord guinness|"
    r"\bsorteo|ofertas?\b|\?\s*$|^¿|^\d+\s|^(c[oó]mo|qu[eé]|cu[aá]l|por qu[eé]|how to|why you|what to)\b|seg[uú]n (los )?(expertos|psic|nutri|un experto)|\|\s*letters|rutinas?\b|recetas?\b|\bdieta\b)",
    re.I,
)

# Para pistas de subreddits "edificantes" (la comunidad ya las marcó como buenas) solo se excluye lo grave.
UPLIFTING_SUBS = {"UpliftingNews", "HumansBeingBros", "MadeMeSmile"}
NEG_HARD = re.compile(
    r"(\bkill|\bdies\b|\bdied\b|\bdeath|\bdead\b|murder|\bwar\b|attack|shooting|terror|scandal|celebrit|"
    r"midterm|turnout|election|lottery|lotto|\bmuer|asesin|guerra|ataque|tiroteo|esc[aá]ndalo|loter[ií]a)", re.I)

POS_STRONG = re.compile(
    r"(breakthrough|\bcures?\b|\bcured\b|eradicat|eliminat(ed|es) (malaria|polio|trachoma|hiv|tb|disease|sleeping)|"
    r"approv(ed|es|al)|vaccin|restor|rewild|reforest|replant|recover(s|ed|y)?\b|rescu|\bsav(e|ed|es|ing)\b|"
    r"donat|volunteer|record low|lowest (level|rate|ever)|lifted out of|milestone|landmark|comeback|rebound|"
    r"bounce[sd]? back|new species|protect(ed|s|ion)? (\d+|area|zone|status|forest|ocean|land)|protected area|marine (reserve|park|protected)|"
    r"national park|renewable|solar|wind (power|farm|energy)|clean energy|heat pump|free (school|meals|care|treatment)|"
    r"life-?saving|reverses?|regrow|prevent|reduc(e|es|ed|ing) (deaths|risk|emissions|poverty|crime|mortality)|"
    r"(deaths|poverty|emissions|mortality|cases|infections|collisions) (fall|fell|drop|dropp|down|plummet|halv)|"
    r"plummet|halved|cut .{0,20} by \d+%|down \d+%|ban(s|ned)? (on )?(single-use|plastic|child marriage|bottom trawl)|"
    r"kindness|good samaritan|reunit|pays? off|paid off|gave away|gives back|\bhero(es|ic)?\b|"
    r"new species|rediscover|thriv|flourish|boom(s|ing)?\b|surge in (solar|wind|renewable)|"
    r"wins? (right|legal|landmark)|grant(s|ed)? (right|asylum|access)|legaliz|abolish|outlaw|"
    r"avance|\bcura\b|curan|erradica|elimina(n|da|do)? (la |el )?(malaria|polio|enfermedad|tracoma|vih)|"
    r"aprueba|aprobad|vacuna|restaura|reforesta|recupera|rescat|\bsalva|donaci|\bdona\b|donan|voluntari|"
    r"m[ií]nimo hist[oó]rico|\bhito\b|[aá]rea protegida|reserva marina|"
    r"parque nacional|renovable|energ[ií]a (solar|e[oó]lica|limpia)|gratuit|nuevas? especies?|"
    r"redescub|reduce (la|el|las|los) (mortalidad|muertes|pobreza|emisiones|riesgo)|baja (la|el) (pobreza|mortalidad)|"
    r"previene|revierte|solidari|h[eé]roe|reencuentr|regala)",
    re.I,
)
POS_WEAK = re.compile(
    r"(new (treatment|therapy|drug|test|technique|method|way|tool|material)|discover|innovat|invent|"
    r"improv|boost|success|helps?\b|helping|hope|kind\b|generous|community|celebrat|award|honou?r|"
    r"adopt|solution|gift|could (help|transform|treat|turn|make)|may (help|treat)|promising|"
    r"efficien|access to|clean water|literacy|school|education|equal|empower|inclus|repair|"
    r"descubr|innova|invent|mejor(a|an)|ayuda|soluci[oó]n|premi|comunidad|acceso a|agua potable|"
    r"educaci[oó]n|igualdad|inclusi|repara|hist[oó]ric|regresa|vuelve a|esperanza|logra|consigue|[eé]xito|"
    r"first (time|ever)|returns? (to|after)|detect|new test|transplant|trasplant|nuevo (tratamiento|f[aá]rmaco|m[eé]todo)|podr[ií]a (ayudar|tratar))",
    re.I,
)

SUB_RX = [
    ("acciones", re.compile(r"(donat|volunteer|kindness|good samaritan|stranger|\bhero|rescu|gave away|gives back|"
                            r"reunit|pays? it forward|paid off .{0,20}debt|generous|selfless|teen (who|raises)|"
                            r"dona|voluntari|h[eé]roe|rescat|desinteresad|gesto|solidari|reencuentr|regala)", re.I)),
    ("salud", re.compile(r"(health|cardi|cpr\b|reanimaci|medic|vaccin|\bdrugs?\b|cancer|disease|patient|hospital|treatment|therap|malaria|"
                         r"\bhiv\b|tubercul|\btb\b|diabet|alzheimer|dementia|surgery|transplant|blood|heart|brain|"
                         r"infection|antibiot|mental health|nurse|doctor|clinic|immun|tumou?r|"
                         r"salud|m[eé]dic|vacuna|f[aá]rmaco|c[aá]ncer|enfermedad|paciente|tratamiento|terapia|"
                         r"cirug|trasplante|sangre|coraz[oó]n|cerebr|infecci|hospital)", re.I)),
    ("ambiente", re.compile(r"(species|wildlife|forest|conservation|ocean|\bsea\b|coral|reef|renewable|solar|wind|"
                            r"emission|climate|rewild|\bbirds?\b|whale|turtle|river|wetland|plastic|biodivers|"
                            r"habitat|\btrees?\b|seagrass|mangrove|beaver|wolf|wolves|bison|lynx|otter|clean energy|"
                            r"heat pump|carbon|electric (car|bus|vehicle)|\bevs?\b|shark|gorilla|leopard|tortoise|rhino|elephant|\bbears?\b|tiger|\bape|animal|tibur[oó]n|gorila|rinoceronte|elefante|\boso\b|tigre|animal|"
                            r"especie|fauna|bosque|conservaci|oc[eé]ano|\bmar\b|arrecife|renovable|emisiones|clima|"
                            r"ballena|tortuga|\br[ií]o\b|humedal|pl[aá]stico|biodivers|[aá]rbol|manglar|carbono)", re.I)),
    ("social", re.compile(r"(poverty|education|school|literacy|rights|equality|women|girls|wage|workers|workweek|"
                          r"housing|homeless|refugee|child marriage|minimum|pension|indigenous|tribe|ancestral|"
                          r"disab|lgbt|vote|voter|democra|inequal|hunger|\bfood\b|jobs|employment|landmine|"
                          r"pobreza|educaci|escuela|alfabetiz|derechos|igualdad|mujeres|ni[nñ]as|salario|"
                          r"trabajador|jornada|vivienda|refugiad|ind[ií]gena|discapacid|hambre|empleo)", re.I)),
    ("comunidad", re.compile(r"(community|local|neighbou?r|town|village|library|park\b|garden|residents|city|"
                             r"council|repair caf|festival|coopera|"
                             r"comunidad|vecin|barrio|pueblo|biblioteca|parque|huerto|municipio|ciudad|cooperativa)", re.I)),
    ("ciencia", re.compile(r"(scien|research|discover|telescope|nasa|\besa\b|space|physic|robot|\bai\b|artificial intell|"
                           r"battery|technolog|engineer|quantum|satellite|fossil|astronom|chemist|"
                           r"cient[ií]f|investigador|descubr|telescopio|espacio|f[ií]sica|robot|inteligencia artificial|"
                           r"bater[ií]a|tecnolog|ingenier|cu[aá]ntic|sat[eé]lite|f[oó]sil)", re.I)),
]


def subtopic(text: str, default: str, deeds_first: bool = True) -> str:
    hits = {k: len(rx.findall(text)) for k, rx in SUB_RX}
    if deeds_first and hits["acciones"]:
        return "acciones"
    best = max(hits, key=lambda k: (hits[k], k == default))
    return best if hits[best] else default


# Impacto medible: aprobaciones, curas, leyes, récords, conservación, programas a gran escala, cifras.
IMPACT = re.compile(
    r"(approv|aprueba|aprobad|\blaws?\b|\bley(es)?\b|\bbill\b|passes|signs|legaliz|\bban(s|ned)?\b|proh[ií]b|"
    r"\bcures?\b|\bcura\b|eradicat|erradic|eliminat|elimina|record|r[eé]cord|first-ever|phase \d|\btrials?\b|ensayo|"
    r"vaccin|vacuna|protect|proteg|national park|parque nacional|reserve|reserva|restor|restaura|reforest|"
    r"new species|nuevas? especies?|population|poblaci[oó]n|programm?e?\b|programa|nationwide|million|mill[oó]n|millones|"
    r"billion|thousands?|miles de|\d[\d,.]*\s?(%|percent|por ciento|hectares?|hect[aá]reas?|acres|km|homes|hogares|people|"
    r"personas|children|ni[nñ]os|students|estudiantes|families|familias|species|tons|toneladas|gw|mw|schools|escuelas)|"
    r"[$€£]\s?\d|poverty|pobreza|free (care|meals|school|surgery|surgeries|treatment|orthopaedic)|gratuit|universal|"
    r"\bfda\b|\bema\b|treaty|tratado|agreement|acuerdo|reduc|cut .{0,25} by|down \d|fell|drop|halv|m[ií]nimo|"
    r"doubl|tripl|renewable|renovable|solar|turbine|\bbred\b|hatch|reintroduc|reintrodu|return(ed)? to the wild|"
    r"remov.{0,30}(traps|plastic|nets|waste|trash)|ghost\W{0,2} (traps|nets|gear)|clean-?ups?\b|limpieza|forgiv|debt relief|housing|vivienda|workweek|jornada|"
    r"transplant|trasplant|surgery|cirug|treatment|tratamiento|antiviral|therapy|terapia|recover(y|ed|ing)|thriv)",
    re.I,
)
# Relleno "feel-good": famosos, marcas, momentos tiernos, arte, gestos virales sin impacto más amplio.
FLUFF = re.compile(
    r"(celebrit|famos[oa]s?|celebridad|taylor swift|julia roberts|beyonc|oprah|mrbeast|barbie|named by|"
    r"cards against humanity|lego\b|disney|netflix|heartwarming|adorable|\bcute\b|wholesome|tierno|conmovedor|"
    r"viral|goes viral|surprise|sorpresa|full[- ]circle|moment\b|momento|proposal|wedding|boda|birthday|cumplea|"
    r"co-?pilot|homework|lemonade|hidden message|pumpkin|puppy|kitten|\bart\b|artist|artwork|painting|painter|"
    r"exhibition|photograph|mural|sculpt|\bnovel\b|\bfilm\b|\bsong\b|album|artista|pintur|exposici[oó]n|"
    r"in awe|awe-inspiring|stunning|sumptuous|incredible|amazing|asombros|impresionante|dream come true|sue[nñ]o cumplido)",
    re.I,
)
# Titulares que nombran el problema pero cuya acción es positiva ("ley que protege a periodistas de demandas abusivas").
REMEDY = re.compile(
    r"(\blaws?\b|\bley\b|\bbill\b|\bact\b|protect|proteg|shield|\bbans?\b|banned|prohib|proh[ií]be|outlaw|abolish|"
    r"aboli|\bends?\b|ending|tackl|combat|curb|reduc|\bcuts?\b|prevent|previen|eliminat|elimina|eradicat|erradica|"
    r"clean(s|ed)? up|limpia|solv|resuelve|court (rules|backs|orders)|"
    r"ruling|fallo|wins? (right|case|fight|battle)|gana)",
    re.I,
)
REMEDY_BLOCK = re.compile(
    r"(\bkill|\bdies\b|\bdied\b|\bdeath|\bdead\b|murder|\bwar\b|attack|\bbomb|shooting|terror|scandal|"
    r"celebrit|trump|putin|tariff|protest|riot|denies|controvers|fails?|\bmuer|asesin|guerra|ataque|bomba|tiroteo|"
    r"esc[aá]ndalo|arancel|protesta|niega|pol[eé]mica|fracas|porn|\bsex|incest|backfire|\brisks?\b|riesgo|"
    r"aren.t sure|warn|advierte|rise in|aumento de|wake-up call|squishy|juguete)",
    re.I,
)
# Descubrimientos científicos concretos (resultado ya obtenido, no promesa).
SCI_IMPACT = re.compile(
    r"(\bfirst\b|discover(s|ed|y)?|new (method|technique|way|material|species|drug|test|tool|map)|confirm(s|ed)?|"
    r"detect(s|ed)?|breakthrough|record|\bmaps?\b|mapped|decod(e|es|ed)|sequenc(e|ed)|successful(ly)?|milestone|"
    r"identif(y|ies|ied)|reveal(s|ed)?|observ(e|es|ed)|measur(e|es|ed)|solv(e|es|ed)|creat(e|es|ed)|build(s)?|built|"
    r"develop(s|ed)?|launch(es|ed)?|lands?\b|landed|achiev|"
    r"primer[oa]?\b|descubr|nuevo (m[eé]todo|material|f[aá]rmaco)|nueva (t[eé]cnica|especie|herramienta)|confirma|"
    r"detecta|hallazgo|hallan|r[eé]cord|mapa|descifra|secuencia|con [eé]xito|logran|identifican|revelan|observan|"
    r"miden|resuelven|crean|desarrollan|lanza|aterriza)",
    re.I,
)
# Promesas, hype y explicativos/consejos: no cuentan como descubrimiento.
SCI_HYPE = re.compile(
    r"(aims? to|plans? to|\bcould\b|\bmay\b|\bmight\b|\bwould\b|set to|hopes? to|\bwill\b|podr[ií]a|"
    r"busca|planea|pretende|^why|^how|^what|^is |^are |^can |^do |explain|explica|surpris|stunning|shock|mind-blow|"
    r"astonish|jaw-drop|incredible|amazing|sorprend|impactante|asombros|incre[ií]ble|mystery|misterio|secret|"
    r"secreto|hidden|oculto|scientists (say|warn)|tips?\b|consejos|danger|peligro|harmful|zombie|risk|riesgo|"
    r"linked to|vinculad|asociad|\bto (conduct|launch|test|study|build|develop|explore)\b|\bawards?\b|"
    r"won.t|doesn.t|isn.t|can.t|no logra)",
    re.I,
)
SCI_SUBJECT = SUB_RX[-1][1]


def sci_score(title: str) -> int:
    if SCI_IMPACT.search(title) and not SCI_HYPE.search(title) and SCI_SUBJECT.search(title):
        return 4
    return 0


FLUFF_LOG: list[tuple[str, str]] = []


def impact_score(title: str, summary: str) -> int:
    return 2 * len(IMPACT.findall(title)) + min(2, len(IMPACT.findall(summary[:300])))


def tone_score(title: str, summary: str):
    """Devuelve (puntaje, motivo de rechazo o None)."""
    if FORMAT_SKIP.search(title):
        return 0, "formato"
    remedy = False
    if NEG_TITLE.search(title):
        # Se salva solo si la acción es claramente positiva y no hay violencia/política dura.
        if REMEDY.search(title) and not REMEDY_BLOCK.search(title) and IMPACT.search(title):
            remedy = True
        else:
            return 0, "negativo"
    if NEG_SUMMARY.search(summary[:300]):
        return 0, "negativo-resumen"
    imp = impact_score(title, summary)
    if FLUFF.search(title) and imp < 2:
        FLUFF_LOG.append((title, "relleno"))
        return 0, "relleno"
    s = 3 * len(POS_STRONG.findall(title)) + len(POS_WEAK.findall(title))
    s += 1 * min(2, len(POS_STRONG.findall(summary[:300])))
    s += 3 if remedy else 0
    if s < 3:
        s += sci_score(title)  # descubrimiento científico concreto
    if s >= 3:  # el impacto solo suma si ya hay una señal clara de progreso (evita "strokes doubled")
        s += min(imp, 6)
    if FLUFF.search(title):
        s -= 4  # relleno con algo de impacto: se queda, pero abajo
    return s, None


# ---------------------------------------------------------------- utilidades
DATE_ALT = re.compile(r"\w+, (\d{1,2})/(\d{1,2})/(\d{4}) - (\d{1,2}):(\d{2})")


def parse_date(raw: str):
    d = A.parse_date(raw)
    if d:
        return d
    m = DATE_ALT.search(raw or "")
    if m:  # NIH: "Wed, 10/14/2026 - 11:00" (hora del este de EE. UU., se toma como UTC-4)
        mo, da, yr, hh, mi = map(int, m.groups())
        return datetime(yr, mo, da, hh, mi, tzinfo=timezone(timedelta(hours=-4))).astimezone(timezone.utc)
    return None


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")


# Fuentes primarias serias: universidades, gobiernos, organismos internacionales y revistas revisadas por pares.
PRIMARY_SUFFIX = re.compile(r"(\.edu|\.ac\.[a-z]{2}|\.edu\.[a-z]{2}|\.gov|\.gov\.[a-z]{2}|\.gob\.[a-z]{2}|\.int)$")
JOURNALS = {"jamanetwork.com", "nejm.org", "thelancet.com", "bmj.com", "cell.com", "pnas.org", "plos.org",
            "journals.plos.org", "sciencenews.org", "nature.com", "science.org", "eurekalert.org", "statnews.com",
            "medicalxpress.com", "phys.org"}


def trusted_domain(d: str, trusted: set[str]) -> bool:
    return bool(PRIMARY_SUFFIX.search(d)) or any(d == t or d.endswith("." + t) for t in trusted | JOURNALS)


def get(url: str, ua: str, timeout=20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en,es;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return r.read(3_000_000)


META_RX = {
    k: re.compile(rf'<meta[^>]+(?:property|name)=["\']{k}["\'][^>]+content=["\']([^"\']+)', re.I)
    for k in ("og:title", "og:description", "article:published_time", "og:site_name", "og:url")
}


def page_meta(url: str):
    """Título/resumen/fecha que publica el propio medio en su página (etiquetas og:)."""
    html = get(url, A.UA, timeout=15).decode("utf-8", "replace")
    out = {}
    for k, rx in META_RX.items():
        m = rx.search(html)
        if not m:  # orden content=... property=...
            m = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{k}["\']', html, re.I)
        out[k] = unescape(m.group(1)).strip() if m else ""
    return out


# ---------------------------------------------------------------- Reddit / 9gag
def reddit_leads():
    leads, status = [], {}

    def one(sub):
        url = f"https://www.reddit.com/r/{sub}/top/.rss?t=day&limit=50"
        try:
            for attempt in range(3):
                try:
                    data = get(url, REDDIT_UA)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code != 429 or attempt == 2:
                        raise
                    time.sleep(8 * (attempt + 1))
            rows = []
            for e in re.findall(rb"<entry>(.*?)</entry>", data, re.S):
                t = re.search(rb"<title>(.*?)</title>", e, re.S)
                c = re.search(rb"<content[^>]*>(.*?)</content>", e, re.S)
                p = re.search(rb'<link href="([^"]+)"', e)
                d = re.search(rb"<(?:published|updated)>(.*?)</", e)
                content = unescape(c.group(1).decode("utf-8", "replace")) if c else ""
                ext = re.findall(r'href="([^"]+)">\[link\]', content)
                rows.append({
                    "sub": sub, "title": unescape(unescape(t.group(1).decode("utf-8", "replace"))) if t else "",
                    "link": ext[0] if ext else "", "permalink": p.group(1).decode() if p else "",
                    "published": d.group(1).decode() if d else "",
                })
            return sub, rows, None
        except Exception as exc:
            return sub, [], f"{type(exc).__name__}: {str(exc)[:120]}"

    for i, sub in enumerate(REDDIT_SUBS):  # en serie y con pausa: Reddit limita mucho a clientes anónimos
        sub, rows, err = one(sub)
        status[sub] = {"ok": err is None, "items": len(rows), "error": err}
        leads.extend(rows)
        time.sleep(2)
    return leads, status


def ninegag_leads():
    try:
        d = json.loads(get(NINEGAG_URL, A.UA))
        posts = d.get("data", {}).get("posts", [])
        return [{"sub": "9gag", "title": p.get("title", ""), "link": "", "permalink": p.get("url", ""),
                 "published": ""} for p in posts], {"ok": True, "items": len(posts), "error": None}
    except Exception as exc:
        return [], {"ok": False, "items": 0, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}


# ---------------------------------------------------------------- principal
def build(now: datetime, general_pool: list[dict], main_feeds: list):
    trusted = set(EXTRA_TRUSTED)
    for f in list(main_feeds) + GOOD_FEEDS:
        trusted.add(domain(f[1]))
    # dominios de los artículos (algunos feeds viven en otro host)
    trusted |= {"theguardian.com", "elpais.com", "goodnewsnetwork.org", "positive.news", "reasonstobecheerful.world",
                "goodgoodgood.co", "mongabay.com", "e360.yale.edu", "canarymedia.com", "ourworldindata.org",
                "anthropocenemagazine.org", "sciencedaily.com", "news.un.org", "nih.gov", "nasa.gov"}

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(A.fetch_feed, GOOD_FEEDS))

    feeds_ok, feeds_failed, cands, rejected = [], [], [], Counter()
    seen = set()

    def add(it):
        key = domain(it["url"]) + urlparse(it["url"]).path.rstrip("/").lower()
        tkey = re.sub(r"\W+", "", A.fold(it["title"].lower()))[:90]
        if key in seen or tkey in seen:
            return False
        seen.add(key)
        seen.add(tkey)
        cands.append(it)
        return True

    for feed, rows, err in results:
        fid, url, source, org, lang, kind, default = feed
        if err or not rows:
            feeds_failed.append({"id": fid, "source": source, "url": url, "error": err or "sin ítems"})
            continue
        kept = 0
        for title, link, date_s, desc in rows:
            u = A.clean_url(link)
            if not u.startswith("http") or A.SKIP_PATH.search(urlparse(u).path.lower()):
                continue
            pub = parse_date(date_s)
            if pub is None or pub > now + timedelta(hours=3) or pub < now - timedelta(hours=GOOD_HOURS):
                continue
            summary = desc if desc and A.fold(desc.lower())[:60] != A.fold(title.lower())[:60] else ""
            score, why = tone_score(title, summary)
            if why:
                rejected[why] += 1
                continue
            need = 1 if kind == "good" else 3
            if score < need:
                rejected["poco positivo"] += 1
                continue
            if kind == "good" and not impact_score(title, summary):
                rejected["relleno (sin impacto medible)"] += 1
                FLUFF_LOG.append((title, "sin impacto medible"))
                continue
            score += 1 if kind == "good" else 0
            if add({"title": title, "url": u, "source": source, "org": org, "lang": lang, "summary": A.trim(summary),
                    "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "_ts": pub.timestamp(), "score": score,
                    "default": default, "feed": fid, "kind": kind, "reddit": []}):
                kept += 1
        feeds_ok.append({"id": fid, "source": source, "url": url, "kind": kind, "itemsInFeed": len(rows), "kept": kept})

    # Notas positivas de los feeds generales (umbral más alto: deben ser claramente de progreso).
    gen_kept = 0
    for it in general_pool:
        if it["_ts"] < (now - timedelta(hours=GENERAL_HOURS)).timestamp():
            continue
        if it["category"] in ("guerras", "sucesos"):
            continue
        score, why = tone_score(it["title"], it["summary"])
        if why or len(POS_STRONG.findall(it["title"])) < 2:
            continue  # en feeds generales se exigen 2 señales fuertes de progreso en el titular
        default = {"ciencias": "ciencia", "finanzas": "social", "politica": "social"}.get(it["category"], "social")
        if add({**{k: it[k] for k in ("title", "url", "source", "org", "lang", "summary", "publishedAt", "_ts")},
                "score": score, "default": default, "feed": it["feed"], "kind": "general", "reddit": []}):
            gen_kept += 1

    # ---------------- Reddit / 9gag: solo pistas
    leads, rstatus = reddit_leads()
    g_leads, gstatus = ninegag_leads()
    reliable_pool = cands + [dict(x, reddit=[]) for x in general_pool]
    lead_log = {"confirmed": 0, "dropped": 0, "confirmedVia": Counter(), "droppedReasons": Counter(), "examples": []}
    by_url = {}
    for it in reliable_pool:
        by_url[domain(it["url"]) + urlparse(it["url"]).path.rstrip("/").lower()] = it

    pool_terms = [(it, set(A.terms(it["title"] + " " + it["summary"][:200]))) for it in reliable_pool]

    def text_match(title):
        """Busca una nota confiable con el mismo hecho (términos distintivos compartidos)."""
        tt = set(A.terms(title))
        best, best_s = None, 0.0
        for it, ot in pool_terms:
            inter = tt & ot
            if len(inter) < 3:
                continue
            s = len(inter) / (len(tt) ** 0.5 * len(ot) ** 0.5 + 1e-9)
            if s > best_s:
                best, best_s = it, s
        return best if best_s >= 0.38 else None

    lead_log["all"] = []

    def attach(it, lead):
        it.setdefault("reddit", [])
        if lead["permalink"] not in [r["url"] for r in it["reddit"]]:
            it["reddit"].append({"sub": lead["sub"], "url": lead["permalink"]})

    meta_jobs = []
    for lead in leads + g_leads:
        if not lead["title"]:
            continue
        link = A.clean_url(lead["link"]) if lead["link"] else ""
        key = domain(link) + urlparse(link).path.rstrip("/").lower() if link else ""
        if key and key in by_url:
            it = by_url[key]
            if it not in cands:  # nota de feed general que aún no estaba: revisar tono con umbral normal
                score, why = tone_score(it["title"], it["summary"])
                if why or score < 3:
                    lead_log["dropped"] += 1; lead_log["all"].append(["descartada", lead["sub"], lead["title"][:120], link])
                    lead_log["droppedReasons"]["medio confiable pero nota no positiva"] += 1
                    continue
                it = dict(it, score=score + 2, default="social", kind="reddit-confirmado")
                add(it)
                by_url[key] = it
            attach(it, lead)
            lead_log["confirmed"] += 1; lead_log["all"].append(["confirmada", lead["sub"], lead["title"][:120], link])
            lead_log["confirmedVia"]["mismo enlace en feed"] += 1
            continue
        if link and trusted_domain(domain(link), trusted):
            meta_jobs.append((lead, link))
            continue
        m = text_match(lead["title"])
        if m is not None and m in cands:
            attach(m, lead)
            lead_log["confirmed"] += 1; lead_log["all"].append(["confirmada", lead["sub"], lead["title"][:120], link])
            lead_log["confirmedVia"]["coincide con nota confiable"] += 1
            continue
        lead_log["dropped"] += 1; lead_log["all"].append(["descartada", lead["sub"], lead["title"][:120], link])
        lead_log["droppedReasons"]["9gag sin fuente" if lead["sub"] == "9gag" else
                                   ("enlace a sitio no verificado" if link else "sin enlace")] += 1
        if len(lead_log["examples"]) < 12:
            lead_log["examples"].append({"sub": lead["sub"], "title": lead["title"][:140], "link": link})

    def fetch_meta(job):
        lead, link = job
        try:
            return lead, link, page_meta(link), None
        except Exception as exc:
            return lead, link, None, f"{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=8) as ex:
        metas = list(ex.map(fetch_meta, meta_jobs))
    for lead, link, meta, err in metas:
        title = (meta or {}).get("og:title", "")
        if not title:
            lead_log["dropped"] += 1; lead_log["all"].append(["descartada", lead["sub"], lead["title"][:120], link])
            lead_log["droppedReasons"]["medio confiable pero no se pudo leer la página"] += 1
            continue
        summary = A.trim(A.clean_text((meta or {}).get("og:description", "")))
        if lead["sub"] in UPLIFTING_SUBS:
            why = "formato" if FORMAT_SKIP.search(title) else ("negativo" if NEG_HARD.search(title) else None)
            score = 3 * len(POS_STRONG.findall(title)) + len(POS_WEAK.findall(title)) + 3 + min(6, impact_score(title, summary))
            if not why and FLUFF.search(title) and impact_score(title, summary) < 2:
                why = "relleno"
                FLUFF_LOG.append((title, "relleno (Reddit)"))
        else:
            score, why = tone_score(title, summary)
        if why or score < 3:
            lead_log["dropped"] += 1; lead_log["all"].append(["descartada", lead["sub"], lead["title"][:120], link])
            lead_log["droppedReasons"]["medio confiable pero nota no positiva"] += 1
            continue
        pub = parse_date(meta.get("article:published_time", "")) or parse_date(lead["published"]) or now
        if pub < now - timedelta(hours=GOOD_HOURS):
            lead_log["dropped"] += 1; lead_log["all"].append(["descartada", lead["sub"], lead["title"][:120], link])
            lead_log["droppedReasons"]["nota antigua"] += 1
            continue
        d = domain(link)
        src = meta.get("og:site_name") or ""
        if not src or len(src) > 40 or src.lower() == title.lower():
            src = PRETTY.get(d, d)
        it = {"title": title, "url": link, "source": src, "org": d, "lang": "es" if d.endswith((".es", ".ar", ".mx", ".cr")) else "en",
              "summary": summary, "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "_ts": pub.timestamp(),
              "score": score + 2, "default": "social", "feed": "reddit-lead", "kind": "reddit-confirmado", "reddit": []}
        if not add(it):
            # ya estaba (mismo titular): marcarlo
            tkey = re.sub(r"\W+", "", A.fold(title.lower()))[:90]
            for c in cands:
                if re.sub(r"\W+", "", A.fold(c["title"].lower()))[:90] == tkey:
                    it = c
                    break
        attach(it, lead)
        lead_log["confirmed"] += 1; lead_log["all"].append(["confirmada", lead["sub"], lead["title"][:120], link])
        lead_log["confirmedVia"]["enlace a medio confiable (leído de su página)"] += 1

    # ---------------- agrupar el mismo hecho entre medios
    idf, df = A.build_vectors(cands)
    groups, sims = A.cluster(cands, idf, df) if len(cands) > 1 else ([[0]] if cands else [], {})
    stories = []
    for g in groups:
        members = [cands[i] for i in g]
        orgs = {m["org"] for m in members}
        best = max(members, key=lambda m: (m["score"], len(m["summary"])))
        es = [m for m in members if m["lang"] == "es"]
        en = [m for m in members if m["lang"] == "en"]
        es_best = max(es, key=lambda m: (m["score"], len(m["summary"]))) if es else None
        en_best = max(en, key=lambda m: (m["score"], len(m["summary"]))) if en else None
        text = " ".join(m["title"] + " " + m["summary"][:200] for m in members)
        sub = subtopic(" ".join(m["title"] for m in members), best["default"])
        if sub == best["default"]:
            sub = subtopic(text, best["default"], deeds_first=False)
        reddit = [r for m in members for r in m.get("reddit", [])]
        ts = [m["_ts"] for m in members]
        stories.append({
            "headline": (es_best or en_best)["title"],
            "headlineLang": "es" if es_best else "en",
            "headlineEs": es_best["title"] if es_best else None,
            "headlineEn": en_best["title"] if en_best else None,
            "summaryEs": es_best["summary"] or None if es_best else None,
            "summaryEsSource": es_best["source"] if es_best and es_best["summary"] else None,
            "summaryEn": en_best["summary"] or None if en_best else None,
            "summaryEnSource": en_best["source"] if en_best and en_best["summary"] else None,
            "subtopic": sub, "subtopicLabel": SUB_LABEL[sub],
            "outlets": len(orgs),
            "outletNames": sorted({m["source"] for m in members}),
            "languages": sorted({m["lang"] for m in members}),
            "firstSeen": A.iso(min(ts)), "lastSeen": A.iso(max(ts)),
            "sources": [{"source": m["source"], "lang": m["lang"], "title": m["title"], "url": m["url"],
                         "publishedAt": m["publishedAt"]} for m in sorted(members, key=lambda m: m["_ts"])],
            "alsoOnReddit": [{"sub": r["sub"], "url": r["url"]} for r in reddit][:3],
            "_rank": best["score"] + 2 * (len(orgs) - 1) + 2 * bool(reddit)
                     - (now.timestamp() - max(ts)) / (36 * 3600),
            "_feeds": sorted({m["feed"] for m in members}),
            "_org": best["org"],
        })

    # Orden: puntaje; luego equilibrio por subtema.
    stories.sort(key=lambda s: s["_rank"], reverse=True)
    per, per_org, chosen = Counter(), Counter(), []
    for s in stories:
        if per[s["subtopic"]] >= SUBTOPIC_MAX.get(s["subtopic"], PER_SUBTOPIC_MAX) or per_org[s["_org"]] >= PER_OUTLET_MAX:
            continue
        per[s["subtopic"]] += 1
        per_org[s["_org"]] += 1
        chosen.append(s)
        if len(chosen) >= MAX_ITEMS:
            break
    chosen.sort(key=lambda s: s["lastSeen"], reverse=True)
    for i, s in enumerate(chosen):
        s["id"] = f"buenas-{i + 1}"
        s.pop("_rank", None)
        s.pop("_feeds", None)
        s.pop("_org", None)

    report = {
        "feedsOk": feeds_ok, "feedsFailed": feeds_failed,
        "knownFails": [{"id": a, "url": b, "error": c} for a, b, c in GOOD_KNOWN_FAILS],
        "leadLog": lead_log.get("all", []),
        "fluffDropped": [t for t, _ in FLUFF_LOG][:40],
        "candidates": len(cands), "fromGeneralFeeds": gen_kept, "rejected": dict(rejected),
        "reddit": rstatus, "ninegag": gstatus,
        "leads": {"total": len(leads) + len(g_leads), "confirmed": lead_log["confirmed"], "dropped": lead_log["dropped"],
                  "confirmedVia": dict(lead_log["confirmedVia"]), "droppedReasons": dict(lead_log["droppedReasons"]),
                  "droppedExamples": lead_log["examples"]},
        "perSubtopic": {k: per.get(k, 0) for k, _ in SUBTOPICS},
        "allStoriesBeforeCap": len(stories),
    }
    return chosen, report
