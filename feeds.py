"""Lista de feeds RSS públicos.

Cada feed: (id, url, medio, organización, idioma, categoría sugerida o None).
"organización" agrupa ediciones del mismo grupo (BBC y BBC Mundo, El País ES/EN,
DW EN/ES, etc.) para que el consenso cuente medios realmente distintos.
"""

FEEDS = [
    # --- BBC ---
    ("bbc-top", "https://feeds.bbci.co.uk/news/rss.xml", "BBC", "bbc", "en", None),
    ("bbc-world", "https://feeds.bbci.co.uk/news/world/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "BBC", "bbc", "en", "politica"),
    ("bbc-business", "https://feeds.bbci.co.uk/news/business/rss.xml", "BBC", "bbc", "en", "finanzas"),
    ("bbc-science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "BBC", "bbc", "en", "ciencias"),
    ("bbc-me", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-us", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-latam", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml", "BBC", "bbc", "en", "mundo"),
    ("bbc-mundo", "https://feeds.bbci.co.uk/mundo/rss.xml", "BBC Mundo", "bbc", "es", None),
    # --- El País ---
    ("elpais-int", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada", "El País", "elpais", "es", "mundo"),
    ("elpais-america", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada", "El País", "elpais", "es", "mundo"),
    ("elpais-esp", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/portada", "El País", "elpais", "es", "politica"),
    ("elpais-eco", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada", "El País", "elpais", "es", "finanzas"),
    ("elpais-soc", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/sociedad/portada", "El País", "elpais", "es", None),
    ("elpais-ciencia", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/ciencia/portada", "El País", "elpais", "es", "ciencias"),
    ("elpais-en", "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada", "El País English", "elpais", "en", None),
    # --- El Mundo / Expansión (Unidad Editorial) ---
    ("elmundo-portada", "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml", "El Mundo", "unidad-editorial", "es", None),
    ("elmundo-int", "https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml", "El Mundo", "unidad-editorial", "es", "mundo"),
    ("elmundo-esp", "https://e00-elmundo.uecdn.es/elmundo/rss/espana.xml", "El Mundo", "unidad-editorial", "es", "politica"),
    ("elmundo-eco", "https://e00-elmundo.uecdn.es/elmundo/rss/economia.xml", "El Mundo", "unidad-editorial", "es", "finanzas"),
    ("elmundo-ciencia", "https://e00-elmundo.uecdn.es/elmundo/rss/ciencia.xml", "El Mundo", "unidad-editorial", "es", "ciencias"),
    ("expansion", "https://e00-expansion.uecdn.es/rss/portada.xml", "Expansión", "unidad-editorial", "es", "finanzas"),
    # --- The Economist, FT, Bloomberg ---
    ("econ-int", "https://www.economist.com/international/rss.xml", "The Economist", "economist", "en", "mundo"),
    ("econ-fin", "https://www.economist.com/finance-and-economics/rss.xml", "The Economist", "economist", "en", "finanzas"),
    ("econ-biz", "https://www.economist.com/business/rss.xml", "The Economist", "economist", "en", "finanzas"),
    ("econ-us", "https://www.economist.com/united-states/rss.xml", "The Economist", "economist", "en", "politica"),
    ("ft-home", "https://www.ft.com/rss/home", "Financial Times", "ft", "en", None),
    ("ft-world", "https://www.ft.com/world?format=rss", "Financial Times", "ft", "en", "mundo"),
    ("ft-markets", "https://www.ft.com/markets?format=rss", "Financial Times", "ft", "en", "finanzas"),
    ("bbg-markets", "https://feeds.bloomberg.com/markets/news.rss", "Bloomberg", "bloomberg", "en", "finanzas"),
    ("bbg-politics", "https://feeds.bloomberg.com/politics/news.rss", "Bloomberg", "bloomberg", "en", "politica"),
    ("bbg-econ", "https://feeds.bloomberg.com/economics/news.rss", "Bloomberg", "bloomberg", "en", "finanzas"),
    # --- Ciencia ---
    ("nature", "https://www.nature.com/nature.rss", "Nature", "nature", "en", "ciencias"),
    ("science", "https://www.science.org/rss/news_current.xml", "Science", "science", "en", "ciencias"),
    ("newscientist", "https://www.newscientist.com/feed/home/", "New Scientist", "newscientist", "en", "ciencias"),
    # --- The Guardian ---
    ("guardian-world", "https://www.theguardian.com/world/rss", "The Guardian", "guardian", "en", "mundo"),
    ("guardian-us", "https://www.theguardian.com/us-news/rss", "The Guardian", "guardian", "en", None),
    ("guardian-politics", "https://www.theguardian.com/politics/rss", "The Guardian", "guardian", "en", "politica"),
    ("guardian-business", "https://www.theguardian.com/uk/business/rss", "The Guardian", "guardian", "en", "finanzas"),
    ("guardian-science", "https://www.theguardian.com/science/rss", "The Guardian", "guardian", "en", "ciencias"),
    ("guardian-env", "https://www.theguardian.com/environment/rss", "The Guardian", "guardian", "en", "ciencias"),
    ("guardian-ukraine", "https://www.theguardian.com/world/ukraine/rss", "The Guardian", "guardian", "en", "guerras"),
    ("guardian-me", "https://www.theguardian.com/world/middleeast/rss", "The Guardian", "guardian", "en", "mundo"),
    # --- NYT ---
    ("nyt-home", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "The New York Times", "nyt", "en", None),
    ("nyt-world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "The New York Times", "nyt", "en", "mundo"),
    ("nyt-politics", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "The New York Times", "nyt", "en", "politica"),
    ("nyt-business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "The New York Times", "nyt", "en", "finanzas"),
    ("nyt-science", "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", "The New York Times", "nyt", "en", "ciencias"),
    # --- NPR ---
    ("npr-news", "https://feeds.npr.org/1001/rss.xml", "NPR", "npr", "en", None),
    ("npr-world", "https://feeds.npr.org/1004/rss.xml", "NPR", "npr", "en", "mundo"),
    ("npr-politics", "https://feeds.npr.org/1014/rss.xml", "NPR", "npr", "en", "politica"),
    ("npr-business", "https://feeds.npr.org/1006/rss.xml", "NPR", "npr", "en", "finanzas"),
    ("npr-science", "https://feeds.npr.org/1007/rss.xml", "NPR", "npr", "en", "ciencias"),
    # --- Al Jazeera, CBS, Sky, CNBC ---
    ("aljazeera", "https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera", "aljazeera", "en", None),
    ("cbs-world", "https://www.cbsnews.com/latest/rss/world", "CBS News", "cbs", "en", "mundo"),
    ("cbs-main", "https://www.cbsnews.com/latest/rss/main", "CBS News", "cbs", "en", None),
    ("sky-world", "https://feeds.skynews.com/feeds/rss/world.xml", "Sky News", "sky", "en", "mundo"),
    ("sky-home", "https://feeds.skynews.com/feeds/rss/home.xml", "Sky News", "sky", "en", None),
    ("cnbc-top", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC", "cnbc", "en", "finanzas"),
    # --- DW ---
    ("dw-en", "https://rss.dw.com/rdf/rss-en-all", "DW", "dw", "en", None),
    ("dw-en-bus", "https://rss.dw.com/rdf/rss-en-bus", "DW", "dw", "en", "finanzas"),
    ("dw-es", "https://rss.dw.com/xml/rss-sp-all", "DW Español", "dw", "es", None),
    # --- France 24 ---
    ("f24-en", "https://www.france24.com/en/rss", "France 24", "france24", "en", None),
    ("f24-en-europe", "https://www.france24.com/en/europe/rss", "France 24", "france24", "en", "mundo"),
    ("f24-en-me", "https://www.france24.com/en/middle-east/rss", "France 24", "france24", "en", "mundo"),
    ("f24-en-biz", "https://www.france24.com/en/business-tech/rss", "France 24", "france24", "en", "finanzas"),
    ("f24-es", "https://www.france24.com/es/rss", "France 24 Español", "france24", "es", None),
    ("f24-es-latam", "https://www.france24.com/es/am%C3%A9rica-latina/rss", "France 24 Español", "france24", "es", "mundo"),
    # --- RFI ---
    ("rfi-en", "https://www.rfi.fr/en/rss", "RFI", "rfi", "en", None),
    ("rfi-es", "https://www.rfi.fr/es/rss", "RFI Español", "rfi", "es", None),
    # --- Euronews ---
    ("euronews-en", "https://www.euronews.com/rss", "Euronews", "euronews", "en", None),
    ("euronews-es", "https://es.euronews.com/rss", "Euronews Español", "euronews", "es", None),
    # --- ONU ---
    ("un-en", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "UN News", "un", "en", "mundo"),
    ("un-es", "https://news.un.org/feed/subscribe/es/news/all/rss.xml", "Noticias ONU", "un", "es", "mundo"),
    # --- Le Monde in English ---
    ("lemonde-en", "https://www.lemonde.fr/en/rss/une.xml", "Le Monde", "lemonde", "en", None),
    # --- España ---
    ("elconfidencial-mundo", "https://rss.elconfidencial.com/mundo/", "El Confidencial", "elconfidencial", "es", "mundo"),
    ("abc", "https://www.abc.es/rss/2.0/portada/", "ABC", "abc", "es", None),
    ("lavanguardia", "https://www.lavanguardia.com/rss/home.xml", "La Vanguardia", "lavanguardia", "es", None),
    ("europapress", "https://www.europapress.es/rss/rss.aspx", "Europa Press", "europapress", "es", None),
    ("20minutos", "https://www.20minutos.es/rss/", "20minutos", "20minutos", "es", None),
    # --- América Latina ---
    ("infobae", "https://www.infobae.com/arc/outboundfeeds/rss/", "Infobae", "infobae", "es", None),
    ("infobae-america", "https://www.infobae.com/arc/outboundfeeds/rss/category/america/", "Infobae", "infobae", "es", "mundo"),
    ("infobae-eco", "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/", "Infobae", "infobae", "es", "finanzas"),
    ("clarin-mundo", "https://www.clarin.com/rss/mundo/", "Clarín", "clarin", "es", "mundo"),
    ("lanacion-ar", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml", "La Nación (Argentina)", "lanacion-ar", "es", None),
    ("eltiempo-mundo", "https://www.eltiempo.com/rss/mundo.xml", "El Tiempo", "eltiempo", "es", "mundo"),
    ("eltiempo-col", "https://www.eltiempo.com/rss/colombia.xml", "El Tiempo", "eltiempo", "es", None),
    ("elcomercio-pe", "https://elcomercio.pe/arc/outboundfeeds/rss/?outputType=xml", "El Comercio (Perú)", "elcomercio-pe", "es", None),
    # --- Costa Rica ---
    ("nacion-cr", "https://www.nacion.com/arc/outboundfeeds/rss/?outputType=xml", "La Nación (Costa Rica)", "grupo-nacion", "es", None),
    ("elfinanciero-cr", "https://www.elfinancierocr.com/arc/outboundfeeds/rss/?outputType=xml", "El Financiero (Costa Rica)", "grupo-nacion", "es", "finanzas"),
    ("elmundo-cr", "https://www.elmundo.cr/feed/", "El Mundo CR", "elmundo-cr", "es", None),
    ("monumental", "https://www.monumental.co.cr/feed/", "Monumental", "monumental", "es", None),
]

# Intentos que no funcionaron (verificados a mano); se listan en el JSON.
KNOWN_FAILS = [
    ("reuters", "https://www.reuters.com/world/rss", "Reuters no ofrece RSS público (401/404)"),
    ("ap", "https://apnews.com/index.rss", "AP no publica un RSS abierto (403)"),
    ("washingtonpost", "https://feeds.washingtonpost.com/rss/world", "Los RSS del Washington Post responden 502"),
    ("cnn-espanol", "https://cnnespanol.cnn.com/feed/", "CNN Español ya no publica RSS (404)"),
    ("efe", "https://efe.com/feed/", "EFE: el feed responde 500 o XML inválido"),
    ("independent", "https://www.independent.co.uk/news/world/rss", "XML inválido"),
    ("wsj-world", "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "Congelado en enero de 2025; no es un feed vivo"),
]
