"""Pestañas regionales: Costa Rica, Centroamérica, Latinoamérica, Sudamérica, Europa,
Asia, África y Australia y Oceanía.

Misma regla que las pestañas de consenso: una historia aparece solo si la publican
5 o más medios distintos (ediciones del mismo grupo cuentan una vez). La región de
cada grupo se decide por los países, ciudades y líderes que nombran sus titulares
y resúmenes, más la región del medio local que la publicó. Una historia puede estar
también en su pestaña temática. Solo código: no hay IA ni se inventa nada.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import urlparse

import actualizar as A

MAX_STORIES = 30

REGIONS = [
    ("costarica", "Costa Rica"),
    ("centroamerica", "Centroamérica"),
    ("latam", "Latinoamérica"),
    ("sudamerica", "Sudamérica"),
    ("europa", "Europa"),
    ("asia", "Asia"),
    ("africa", "África"),
    ("oceania", "Australia y Oceanía"),
]

# (id, url, medio, organización, idioma, región)
REGION_FEEDS = [
    # --- Costa Rica ---
    ("cr-nacion-pais", "https://www.nacion.com/arc/outboundfeeds/rss/category/el-pais/?outputType=xml", "La Nación (Costa Rica)", "grupo-nacion", "es", "costarica"),
    ("cr-lateja", "https://www.lateja.cr/arc/outboundfeeds/rss/?outputType=xml", "La Teja", "grupo-nacion", "es", "costarica"),
    ("cr-observador", "https://observador.cr/feed/", "El Observador", "observador-cr", "es", "costarica"),
    ("cr-delfino", "https://delfino.cr/feed", "Delfino", "delfino", "es", "costarica"),
    ("cr-semanario", "https://semanariouniversidad.com/feed/", "Semanario Universidad", "semanario-universidad", "es", "costarica"),
    ("cr-amprensa", "https://www.amprensa.com/feed/", "AM Prensa", "amprensa", "es", "costarica"),
    ("cr-qcostarica", "https://qcostarica.com/feed/", "Q Costa Rica", "qcostarica", "en", "costarica"),
    # (La Nación portada, El Financiero, El Mundo CR y Monumental ya están en feeds.py)
    # --- Centroamérica ---
    ("ca-prensalibre", "https://www.prensalibre.com/feed/", "Prensa Libre", "prensalibre", "es", "centroamerica"),
    ("ca-republica-gt", "https://republica.gt/feed/", "República (Guatemala)", "republica-gt", "es", "centroamerica"),
    ("ca-lahora-gt", "https://lahora.gt/feed/", "La Hora (Guatemala)", "lahora-gt", "es", "centroamerica"),
    ("ca-cronica-gt", "https://cronica.com.gt/feed/", "Crónica (Guatemala)", "cronica-gt", "es", "centroamerica"),
    ("ca-prensa-pa", "https://www.prensa.com/arc/outboundfeeds/rss/?outputType=xml", "La Prensa (Panamá)", "prensa-pa", "es", "centroamerica"),
    ("ca-critica-pa", "https://www.critica.com.pa/rss.xml", "Crítica (Panamá)", "critica-pa", "es", "centroamerica"),
    ("ca-confidencial", "https://confidencial.digital/feed/", "Confidencial (Nicaragua)", "confidencial-ni", "es", "centroamerica"),
    ("ca-divergentes", "https://www.divergentes.com/feed/", "Divergentes", "divergentes", "es", "centroamerica"),
    ("ca-articulo66", "https://www.articulo66.com/feed/", "Artículo 66", "articulo66", "es", "centroamerica"),
    ("ca-proceso-hn", "https://proceso.hn/feed/", "Proceso Digital (Honduras)", "proceso-hn", "es", "centroamerica"),
    ("ca-criterio-hn", "https://criterio.hn/feed/", "Criterio.hn", "criterio-hn", "es", "centroamerica"),
    ("ca-hondudiario", "https://www.hondudiario.com/feed/", "Hondudiario", "hondudiario", "es", "centroamerica"),
    ("ca-gatoencerrado", "https://gatoencerrado.news/feed/", "Gato Encerrado (El Salvador)", "gatoencerrado", "es", "centroamerica"),
    ("ca-belize", "https://www.breakingbelizenews.com/feed/", "Breaking Belize News", "breakingbelize", "en", "centroamerica"),
    ("ca-bbcmundo-amlat", "https://feeds.bbci.co.uk/mundo/america_latina/rss.xml", "BBC Mundo", "bbc", "es", None),
    # --- México, Caribe y Latinoamérica en general ---
    ("la-eluniversal-mx", "https://www.eluniversal.com.mx/arc/outboundfeeds/rss/?outputType=xml", "El Universal (México)", "eluniversal-mx", "es", "latam"),
    ("la-jornada", "https://www.jornada.com.mx/rss/edicion.xml", "La Jornada", "jornada", "es", "latam"),
    ("la-elfinanciero-mx", "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/?outputType=xml", "El Financiero (México)", "elfinanciero-mx", "es", "latam"),
    ("la-expansion-mx", "https://expansion.mx/rss", "Expansión México", "expansion-mx", "es", "latam"),
    ("la-elpais-mexico", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/mexico/portada", "El País", "elpais", "es", "latam"),
    ("la-infobae-mx", "https://www.infobae.com/arc/outboundfeeds/rss/category/mexico/", "Infobae", "infobae", "es", "latam"),
    ("la-diariolibre", "https://www.diariolibre.com/rss/portada.xml", "Diario Libre (R. Dominicana)", "diariolibre", "es", "latam"),
    ("la-elnuevodia", "https://www.elnuevodia.com/arc/outboundfeeds/rss/?outputType=xml", "El Nuevo Día (Puerto Rico)", "elnuevodia", "es", "latam"),
    ("la-14ymedio", "https://www.14ymedio.com/rss/", "14ymedio (Cuba)", "14ymedio", "es", "latam"),
    ("la-guardian-americas", "https://www.theguardian.com/world/americas/rss", "The Guardian", "guardian", "en", None),
    # --- Sudamérica ---
    ("sa-clarin", "https://www.clarin.com/rss/lo-ultimo/", "Clarín", "clarin", "es", "sudamerica"),
    ("sa-infobae-ar", "https://www.infobae.com/arc/outboundfeeds/rss/category/politica/", "Infobae", "infobae", "es", "sudamerica"),
    ("sa-semana", "https://www.semana.com/arc/outboundfeeds/rss/?outputType=xml", "Semana (Colombia)", "semana", "es", "sudamerica"),
    ("sa-latercera", "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml", "La Tercera (Chile)", "latercera", "es", "sudamerica"),
    ("sa-rpp", "https://rpp.pe/rss", "RPP (Perú)", "rpp", "es", "sudamerica"),
    ("sa-elnacional-ve", "https://www.elnacional.com/feed/", "El Nacional (Venezuela)", "elnacional-ve", "es", "sudamerica"),
    ("sa-efectococuyo", "https://efectococuyo.com/feed/", "Efecto Cocuyo", "efectococuyo", "es", "sudamerica"),
    ("sa-elcomercio-ec", "https://www.elcomercio.com/feed/", "El Comercio (Ecuador)", "elcomercio-ec", "es", "sudamerica"),
    ("sa-abc-py", "https://www.abc.com.py/arc/outboundfeeds/rss/?outputType=xml", "ABC Color (Paraguay)", "abc-py", "es", "sudamerica"),
    ("sa-agenciabrasil", "https://agenciabrasil.ebc.com.br/es/rss/ultimasnoticias/feed.xml", "Agência Brasil", "agenciabrasil", "es", "sudamerica"),
    ("sa-mercopress", "https://en.mercopress.com/rss", "MercoPress", "mercopress", "en", "sudamerica"),
    # --- Europa ---
    ("eu-guardian-europe", "https://www.theguardian.com/world/europe-news/rss", "The Guardian", "guardian", "en", None),
    ("eu-dw-europe", "https://rss.dw.com/rdf/rss-en-eu", "DW", "dw", "en", None),
    ("eu-politico", "https://www.politico.eu/feed/", "Politico Europe", "politico-eu", "en", "europa"),
    ("eu-irishtimes", "https://www.irishtimes.com/arc/outboundfeeds/feed-world/?outputType=xml", "The Irish Times", "irishtimes", "en", None),
    ("eu-rte", "https://www.rte.ie/feeds/rss/?index=/news/", "RTÉ", "rte", "en", "europa"),
    ("eu-thelocal", "https://www.thelocal.com/feeds/rss.php", "The Local", "thelocal", "en", "europa"),
    ("eu-kyivindependent", "https://kyivindependent.com/news-archive/rss/", "The Kyiv Independent", "kyivindependent", "en", "europa"),
    ("eu-ansa", "https://www.ansa.it/english/news/english_nr_rss.xml", "ANSA", "ansa", "en", "europa"),
    ("eu-notesfrompoland", "https://notesfrompoland.com/feed/", "Notes from Poland", "notesfrompoland", "en", "europa"),
    ("eu-balkaninsight", "https://balkaninsight.com/feed/", "Balkan Insight", "balkaninsight", "en", "europa"),
    # --- Asia ---
    ("as-guardian-asia", "https://www.theguardian.com/world/asia-pacific/rss", "The Guardian", "guardian", "en", None),
    ("as-scmp", "https://www.scmp.com/rss/91/feed", "South China Morning Post", "scmp", "en", "asia"),
    ("as-scmp-asia", "https://www.scmp.com/rss/3/feed", "South China Morning Post", "scmp", "en", "asia"),
    ("as-thehindu", "https://www.thehindu.com/news/international/feeder/default.rss", "The Hindu", "thehindu", "en", None),
    ("as-thehindu-nat", "https://www.thehindu.com/news/national/feeder/default.rss", "The Hindu", "thehindu", "en", "asia"),
    ("as-straitstimes", "https://www.straitstimes.com/news/asia/rss.xml", "The Straits Times", "straitstimes", "en", "asia"),
    ("as-cna", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511", "CNA", "cna", "en", "asia"),
    ("as-dawn", "https://www.dawn.com/feeds/home", "Dawn", "dawn", "en", "asia"),
    ("as-hindustantimes", "https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml", "Hindustan Times", "hindustantimes", "en", None),
    ("as-ndtv", "https://feeds.feedburner.com/ndtvnews-world-news", "NDTV", "ndtv", "en", None),
    ("as-indianexpress", "https://indianexpress.com/section/india/feed/", "The Indian Express", "indianexpress", "en", "asia"),
    ("as-bangkokpost", "https://www.bangkokpost.com/rss/data/topstories.xml", "Bangkok Post", "bangkokpost", "en", "asia"),
    ("as-rappler", "https://www.rappler.com/feed/", "Rappler", "rappler", "en", "asia"),
    ("as-dw-asia", "https://rss.dw.com/rdf/rss-en-asia", "DW", "dw", "en", None),
    ("as-f24-asia", "https://www.france24.com/en/asia-pacific/rss", "France 24", "france24", "en", None),
    ("as-thediplomat", "https://thediplomat.com/feed/", "The Diplomat", "thediplomat", "en", "asia"),
    # --- África ---
    ("af-guardian-africa", "https://www.theguardian.com/world/africa/rss", "The Guardian", "guardian", "en", None),
    ("af-allafrica", "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "AllAfrica", "allafrica", "en", "africa"),
    ("af-premiumtimes", "https://www.premiumtimesng.com/feed", "Premium Times", "premiumtimes", "en", "africa"),
    ("af-punch", "https://punchng.com/feed/", "Punch", "punch", "en", "africa"),
    ("af-dailymaverick", "https://www.dailymaverick.co.za/dmrss/", "Daily Maverick", "dailymaverick", "en", "africa"),
    ("af-citizen-za", "https://www.citizen.co.za/feed/", "The Citizen (Sudáfrica)", "citizen-za", "en", "africa"),
    ("af-nation-ke", "https://nation.africa/kenya/rss.xml", "Nation (Kenia)", "nation-ke", "en", "africa"),
    ("af-standard-ke", "https://www.standardmedia.co.ke/rss/headlines.php", "The Standard (Kenia)", "standard-ke", "en", "africa"),
    ("af-africanews", "https://www.africanews.com/feed/rss", "Africanews", "euronews", "en", "africa"),
    ("af-egyptindependent", "https://www.egyptindependent.com/feed/", "Egypt Independent", "egyptindependent", "en", "africa"),
    ("af-f24-africa", "https://www.france24.com/en/africa/rss", "France 24", "france24", "en", None),
    ("af-dw-africa", "https://rss.dw.com/rdf/rss-en-africa", "DW", "dw", "en", None),
    ("af-rfi-africa", "https://www.rfi.fr/en/africa/rss", "RFI", "rfi", "en", None),
    # --- Australia y Oceanía ---
    ("oc-abc-au", "https://www.abc.net.au/news/feed/51120/rss.xml", "ABC News (Australia)", "abc-au", "en", "oceania"),
    ("oc-abc-au2", "https://www.abc.net.au/news/feed/2942460/rss.xml", "ABC News (Australia)", "abc-au", "en", "oceania"),
    ("oc-guardian-au", "https://www.theguardian.com/australia-news/rss", "The Guardian", "guardian", "en", "oceania"),
    ("oc-smh", "https://www.smh.com.au/rss/feed.xml", "The Sydney Morning Herald", "nine", "en", "oceania"),
    ("oc-theage", "https://www.theage.com.au/rss/feed.xml", "The Age", "nine", "en", "oceania"),
    ("oc-crikey", "https://www.crikey.com.au/feed/", "Crikey", "crikey", "en", "oceania"),
    ("oc-conversation-au", "https://theconversation.com/au/articles.atom", "The Conversation", "conversation", "en", "oceania"),
    ("oc-bbc-au", "https://feeds.bbci.co.uk/news/world/australia/rss.xml", "BBC", "bbc", "en", None),
    ("oc-rnz", "https://www.rnz.co.nz/rss/national.xml", "RNZ", "rnz", "en", "oceania"),
    ("oc-rnz-pacific", "https://www.rnz.co.nz/rss/pacific.xml", "RNZ", "rnz", "en", "oceania"),
    ("oc-nzherald", "https://www.nzherald.co.nz/arc/outboundfeeds/rss/curated/78/?outputType=xml", "NZ Herald", "nzherald", "en", "oceania"),
    ("oc-stuff", "https://www.stuff.co.nz/rss", "Stuff", "stuff", "en", "oceania"),
]

REGION_KNOWN_FAILS = [
    ("crhoy", "https://www.crhoy.com/feed/", "404 (sin RSS)"),
    ("teletica", "https://www.teletica.com/rss", "Devuelve HTML, no RSS"),
    ("ticotimes", "https://ticotimes.net/feed", "Respuesta comprimida ilegible (brotli)"),
    ("ameliarueda", "https://www.ameliarueda.com/feed/", "404"),
    ("crc891 / elobservador.cr / trece.cr / elpais.cr", "-", "Error de conexión TLS"),
    ("diarioextra / laprensalibre.cr", "-", "403"),
    ("repretel / elguardian.cr / ncr", "-", "Sin notas recientes"),
    ("la prensa gráfica / elsalvador.com / laprensa.com.ni", "-", "403"),
    ("el faro / soy502", "-", "Devuelve HTML o XML inválido"),
    ("el heraldo hn / la prensa hn / tvn panamá / la estrella panamá", "-", "404"),
    ("milenio / proceso.com.mx / animal político / listín diario / cubadebate", "-", "404 / 403 / 504 / TLS"),
    ("página 12 / biobío / emol / la república pe / el país uy / el deber / primicias / el espectador", "-", "404 / 403 / TLS / XML inválido / vacío"),
    ("swissinfo / kyodo / nhk / yonhap / korea herald / nikkei / spiegel intl", "-", "404 / TLS / sin notas recientes"),
    ("mail & guardian / news24 / the east african / ghanaweb", "-", "404 / TLS / 403 / XML inválido"),
    ("sbs / news.com.au / 9news / fiji times", "-", "Sin notas recientes / XML inválido / 404"),
    ("al jazeera por región", "https://www.aljazeera.com/where/<región>/rss", "404 (se usa el feed general de Al Jazeera)"),
    ("tagesschau / yle / nos / g1 / folha / japan times", "-", "Funcionan pero no están en español ni inglés (no se pueden agrupar)"),
]


# Feeds de feeds.py que son medios locales de una región.
MAIN_FEED_REGION = {
    "nacion-cr": "costarica", "elfinanciero-cr": "costarica", "elmundo-cr": "costarica", "monumental": "costarica",
    "clarin-mundo": "sudamerica", "lanacion-ar": "sudamerica", "eltiempo-col": "sudamerica",
    "elcomercio-pe": "sudamerica", "infobae-america": None,
}


def _rx(words):
    return re.compile(r"(?<![a-z])(" + "|".join(words) + r")(?![a-z])")


# Palabras en minúsculas y sin tildes (se compara contra texto "plegado").
KW = {
    "costarica": _rx([r"costa rica", r"costarricens\w*", r"ticos?", r"ticas?", r"guanacaste", r"puntarenas", r"limon",
                      r"cartago", r"heredia", r"alajuela", r"oij", r"ccss", r"aresep", r"mopt", r"bccr", r"sugef",
                      r"rodrigo chaves", r"chaves", r"laura fernandez", r"asamblea legislativa", r"sala iv",
                      r"sala constitucional", r"ucr", r"pln", r"pusc", r"frente amplio", r"san jose", r"zapote",
                      r"cuesta de moras", r"recope", r"\bice\b", r"aya", r"conavi", r"micitt", r"mep"]),
    "centroamerica": _rx([r"centroamerica\w*", r"central america\w*", r"guatemal\w*", r"hondur\w*", r"el salvador",
                          r"salvadoren\w*", r"salvador\w*n", r"nicaragu\w*", r"panama\w*", r"belice", r"belize\w*",
                          r"bukele", r"ortega", r"murillo", r"arevalo", r"mulino", r"asfura", r"nasralla",
                          r"tegucigalpa", r"managua", r"san salvador", r"sica", r"canal de panama", r"panama canal",
                          r"darien"]),
    "latam": _rx([r"mexic\w*", r"sheinbaum", r"cdmx", r"ciudad de mexico", r"mexico city", r"morena", r"monterrey",
                  r"guadalajara", r"sinaloa", r"jalisco", r"tijuana", r"cuba\w*", r"la habana", r"havana", r"haiti\w*",
                  r"republica dominicana", r"dominican\w*", r"puerto ric\w*", r"caribe", r"caribbean", r"jamaica\w*",
                  r"trinidad", r"bahamas", r"latinoamerica\w*", r"latin america\w*", r"america latina", r"celac",
                  r"abinader", r"diaz-canel", r"cartel"]),
    "sudamerica": _rx([r"argentin\w*", r"milei", r"buenos aires", r"brasil\w*", r"brazil\w*", r"lula", r"bolsonaro",
                       r"sao paulo", r"rio de janeiro", r"chile\w*", r"kast", r"boric", r"colombia\w*", r"petro",
                       r"bogota", r"medellin", r"peru\w*", r"lima", r"venezuel\w*", r"maduro", r"machado",
                       r"delcy", r"caracas", r"ecuador\w*", r"noboa", r"quito", r"guayaquil", r"bolivia\w*", r"la paz",
                       r"paraguay\w*", r"asuncion", r"uruguay\w*", r"montevideo", r"guyan\w*", r"surinam\w*",
                       r"mercosur", r"sudamerica\w*", r"south america\w*", r"falklands", r"malvinas", r"amazon(ia|as)"]),
    "europa": _rx([r"europ\w*", r"union europea", r"european union", r"\beu\b", r"\bue\b", r"bruselas", r"brussels",
                   r"von der leyen", r"uk", r"britain", r"british", r"britanic\w*", r"reino unido", r"england",
                   r"london", r"londres", r"starmer", r"scotland", r"escocia", r"wales", r"ireland",
                   r"irlanda", r"irish", r"france", r"francia", r"french", r"frances\w*", r"macron", r"paris",
                   r"germany", r"german", r"alemani\w*", r"aleman\w*", r"merz", r"berlin", r"italy", r"italia\w*",
                   r"italian\w*", r"meloni", r"roma", r"rome", r"spain", r"spanish", r"espana", r"madrid",
                   r"barcelona", r"catalun\w*", r"portugal", r"portugu\w*", r"lisboa", r"lisbon", r"netherlands",
                   r"dutch", r"paises bajos", r"belgi\w*", r"poland", r"polish", r"polonia", r"ukrain\w*",
                   r"ucrania\w*", r"kyiv", r"kiev", r"zelensk\w*", r"russia\w*", r"rusia", r"ruso", r"rusos",
                   r"kremlin", r"putin", r"moscow", r"moscu", r"sweden", r"suecia", r"norway", r"noruega",
                   r"finland\w*", r"denmark", r"dinamarca", r"greece", r"grecia", r"greek", r"hungar\w*", r"orban",
                   r"romania\w*", r"rumania", r"czech", r"austria\w*", r"switzerland", r"suiza", r"swiss", r"nato",
                   r"otan", r"vatican\w*", r"vaticano", r"pope", r"papa leon", r"leon xiv", r"serbia\w*", r"kosovo",
                   r"balkan\w*", r"baltic", r"moldova", r"slovak\w*", r"croatia", r"bulgaria\w*", r"albania\w*",
                   r"channel tunnel", r"nord stream", r"black sea", r"mar negro", r"belarus", r"bielorrusia",
                   r"lithuania\w*", r"lituania", r"latvia", r"estonia", r"sanchez", r"feijoo", r"psoe"]),
    "asia": _rx([r"china", r"chinese", r"chin[oa]s?", r"beijing", r"pekin", r"xi jinping", r"taiwan\w*", r"hong kong",
                 r"japan\w*", r"japon\w*", r"tokyo", r"tokio", r"takaichi", r"korea\w*", r"corea\w*", r"seoul", r"seul",
                 r"pyongyang", r"kim jong", r"india", r"indian", r"modi", r"delhi", r"mumbai",
                 r"pakistan\w*", r"afghan\w*", r"afgan\w*", r"taliban", r"bangladesh\w*", r"sri lanka", r"nepal\w*",
                 r"myanmar", r"thailand", r"thai", r"tailandia", r"vietnam\w*", r"cambodia\w*", r"camboya",
                 r"malaysia\w*", r"malasia", r"singapore\w*", r"singapur", r"indonesia\w*", r"jakarta",
                 r"philippin\w*", r"filipin\w*", r"manila", r"marcos", r"mongolia", r"kazakh\w*", r"asia\w*",
                 r"israel\w*", r"gaza", r"hamas", r"netanyahu", r"palestin\w*", r"west bank", r"cisjordania",
                 r"lebanon", r"libano", r"hezbollah", r"hezbola", r"syria\w*", r"siria", r"iran\w*", r"tehran",
                 r"teheran", r"iraq\w*", r"irak", r"saudi", r"saudi\w*", r"arabia saudi\w*", r"yemen\w*",
                 r"houthi\w*", r"huties", r"qatar\w*", r"catar", r"emirat\w*", r"dubai", r"jordan", r"jordania",
                 r"oriente medio", r"middle east", r"turkey", r"turquia", r"erdogan"]),
    "africa": _rx([r"africa\w*", r"nigeria\w*", r"tinubu", r"lagos", r"abuja", r"kenya\w*", r"kenia", r"nairobi", r"ruto",
                   r"south africa\w*", r"sudafrica\w*", r"ramaphosa", r"johannesburg", r"cape town", r"ethiopia\w*",
                   r"etiopia", r"abiy", r"egypt\w*", r"egipt\w*", r"cairo", r"sudan\w*", r"darfur", r"congo\w*",
                   r"drc", r"kinshasa", r"ghana\w*", r"senegal\w*", r"mali", r"niger", r"burkina", r"morocc\w*",
                   r"marruec\w*", r"algeria\w*", r"argelia", r"tunisia\w*", r"tunez", r"libya\w*", r"libia",
                   r"somali\w*", r"uganda\w*", r"tanzania\w*", r"rwanda\w*", r"ruanda", r"zimbabwe\w*", r"mozambi\w*",
                   r"angola\w*", r"cameroon\w*", r"camerun", r"madagascar", r"sahel", r"eritrea\w*", r"zambia\w*",
                   r"malawi\w*", r"namibia\w*", r"botswana", r"ivory coast", r"costa de marfil", r"sierra leone",
                   r"liberia\w*", r"guinea"]),
    "oceania": _rx([r"australia\w*", r"albanese", r"sydney", r"melbourne", r"canberra", r"queensland", r"brisbane",
                    r"perth", r"adelaide", r"tasmania", r"victoria police", r"new south wales", r"nsw",
                    r"new zealand\w*", r"nueva zelanda", r"luxon", r"wellington", r"auckland", r"fiji\w*",
                    r"papua", r"samoa\w*", r"tonga\w*", r"solomon islands", r"vanuatu", r"pacific island\w*",
                    r"cook islands", r"oceania", r"maori"]),
}
US = _rx([r"estados unidos", r"eeuu", r"ee\.uu", r"united states", r"u\.s", r"trump", r"washington",
          r"white house", r"casa blanca", r"congress", r"congreso de ee", r"oregon", r"texas", r"california",
          r"new york", r"nueva york", r"florida", r"pentagon\w*", r"pentagono"])


MAIN_ORG = {"nacion-cr": "grupo-nacion", "elfinanciero-cr": "grupo-nacion", "elmundo-cr": "elmundo-cr",
            "monumental": "monumental", "clarin-mundo": "clarin", "lanacion-ar": "lanacion-ar",
            "eltiempo-col": "eltiempo", "elcomercio-pe": "elcomercio-pe"}


def fold(s):
    return A.fold(s).lower()


def region_votes(members):
    votes, kw_orgs, local_orgs = Counter(), {}, {}
    us = 0
    for m in members:
        t = fold(m["title"])
        su = fold(m["summary"][:200])
        for r, rx in KW.items():
            n = 2 * len(rx.findall(t)) + len(rx.findall(su))
            if n:
                votes[r] += n
                kw_orgs.setdefault(r, set()).add(m["org"])
        us += 2 * len(US.findall(t)) + len(US.findall(su))
        if m.get("region"):
            local_orgs.setdefault(m["region"], set()).add(m["org"])
    return votes, us, kw_orgs, local_orgs


def pick_region(members):
    """Región de un grupo: la más nombrada, pero solo si al menos 2 medios distintos nombran
    un lugar de esa región y, entre medios que la nombran y medios locales de ella, suman
    la mitad de los medios del grupo. Así una noticia global (p. ej. un producto de Tesla)
    no cae en una región solo porque la cubren medios de allí."""
    votes, us, kw_orgs, local_orgs = region_votes(members)
    if not votes:
        return None, votes
    best, n = votes.most_common(1)[0]
    # Costa Rica es parte de Centroamérica: si hay señales de ambas y CR pesa, va a Costa Rica.
    if best == "centroamerica" and votes.get("costarica", 0) >= n * 0.6:
        best, n = "costarica", votes["costarica"]
    if us > n * 1.5:
        return None, votes          # historia sobre todo de EE. UU.
    orgs = {m["org"] for m in members}
    named = kw_orgs.get(best, set())
    support = named | local_orgs.get(best, set())
    if len(named) < 2 or len(support) * 2 < len(orgs):
        return None, votes
    return best, votes


def build(now, general_pool, main_feed_urls):
    feeds = [f for f in REGION_FEEDS if f[1] not in main_feed_urls]
    with ThreadPoolExecutor(max_workers=24) as ex:
        results = list(ex.map(A.fetch_feed, feeds))

    pool, seen = [], set()

    def keys(url, org, title):
        p = urlparse(url)
        return ((p.netloc.replace("www.", "") + p.path.rstrip("/")).lower(),
                org + "|" + re.sub(r"\W+", "", A.fold(title.lower()))[:90])

    for it in general_pool:
        k1, k2 = keys(it["url"], it["org"], it["title"])
        seen.update((k1, k2))
        pool.append({k: it[k] for k in ("title", "url", "source", "org", "lang", "summary", "publishedAt", "_ts")}
                    | {"region": MAIN_FEED_REGION.get(it.get("feed"))})

    feeds_ok, feeds_failed = [], []
    for feed, rows, err in results:
        fid, url, source, org, lang, region = feed
        if err or not rows:
            feeds_failed.append({"id": fid, "source": source, "url": url, "error": err or "sin ítems"})
            continue
        kept = 0
        for title, link, date_s, desc in rows:
            if len(title) < 18 or A.SKIP_TITLE.search(title) or A.SECTION_TITLE.search(title):
                continue
            u = A.clean_url(link)
            if not u.startswith("http") or A.SKIP_PATH.search(urlparse(u).path.lower()):
                continue
            pub = A.parse_date(date_s)
            if pub is None or pub > now + timedelta(hours=3) or pub < now - timedelta(hours=A.NEWS_HOURS):
                continue
            k1, k2 = keys(u, org, title)
            if k1 in seen or k2 in seen:
                continue
            seen.update((k1, k2))
            summary = desc if desc and A.fold(desc.lower())[:60] != A.fold(title.lower())[:60] else ""
            pool.append({"title": title, "url": u, "source": source, "org": org, "lang": lang,
                         "summary": A.trim(summary), "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "_ts": pub.timestamp(), "region": region})
            kept += 1
        feeds_ok.append({"id": fid, "source": source, "org": org, "region": region, "url": url,
                         "itemsInFeed": len(rows), "kept": kept})

    idf, df = A.build_vectors(pool)
    groups, sims = A.cluster(pool, idf, df)

    by_region = defaultdict(list)
    near = Counter()   # grupos con 3-4 medios por región (para el informe)
    debug = []
    for g in groups:
        members = [pool[i] for i in g]
        k = len({m["org"] for m in members})
        if k < 3:
            continue
        region, votes = pick_region(members)
        if not region:
            continue
        debug.append((region, k, members))
        if k < A.MIN_OUTLETS:
            near[region] += 1
            continue
        s = A.make_story(g, pool, sims)
        s["region"] = region
        by_region[region].append(s)

    cats = []
    counts = {}
    for rid, label in REGIONS:
        lst = sorted(by_region.get(rid, []), key=lambda s: (s["outlets"], s["_last"]), reverse=True)[:MAX_STORIES]
        for i, s in enumerate(lst):
            s.pop("_last", None)
            s["id"] = f"{rid}-{i + 1}"
        counts[rid] = len(lst)
        cats.append({"id": rid, "label": label, "group": "region", "minOutlets": A.MIN_OUTLETS, "stories": lst})

    report = {
        "minOutlets": A.MIN_OUTLETS,
        "feedsOk": feeds_ok, "feedsFailed": feeds_failed,
        "knownFails": [{"id": a, "url": b, "error": c} for a, b, c in REGION_KNOWN_FAILS],
        "itemsGathered": len(pool), "clusters": len(groups),
        "perRegion": counts,
        "groupsWith3or4Outlets": {r: near.get(r, 0) for r, _ in REGIONS},
        "workingLocalOutletsPerRegion": {
            r: len({f["org"] for f in feeds_ok if f["region"] == r and f["kept"]}
                   | {o for fid, o in MAIN_ORG.items() if MAIN_FEED_REGION.get(fid) == r})
            for r, _ in REGIONS},
    }
    return cats, report, debug
