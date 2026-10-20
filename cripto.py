"""Pestaña "Criptomonedas": consenso estricto, solo con código.

Una historia aparece solo si la publican 3 o más medios distintos (misma regla de
"organización" que el resto de pestañas: ediciones del mismo grupo cuentan una vez).
Usa los feeds generales/financieros de la app más medios cripto y de negocios
reconocidos. Se descartan comunicados de prensa, contenido patrocinado,
predicciones de precio, listas de "monedas para comprar" y airdrops/promoción.
No inventa nada: titulares y resúmenes salen tal cual de cada medio.
"""
from __future__ import annotations

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import quote, urlparse

import actualizar as A

MIN_OUTLETS = 3
MAX_STORIES = 30

# (id, url, medio, organización, idioma, solo_cripto)
CRYPTO_FEEDS = [
    ("cr-coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk", "coindesk", "en", True),
    ("cr-theblock", "https://www.theblock.co/rss.xml", "The Block", "theblock", "en", True),
    ("cr-decrypt", "https://decrypt.co/feed", "Decrypt", "decrypt", "en", True),
    ("cr-cointelegraph", "https://cointelegraph.com/rss", "Cointelegraph", "cointelegraph", "en", True),
    ("cr-cointelegraph-btc", "https://cointelegraph.com/rss/tag/bitcoin", "Cointelegraph", "cointelegraph", "en", True),
    ("cr-protos", "https://protos.com/feed/", "Protos", "protos", "en", True),
    ("cr-defiant", "https://thedefiant.io/api/feed", "The Defiant", "defiant", "en", True),
    ("cr-unchained", "https://unchainedcrypto.com/feed/", "Unchained", "unchained", "en", True),
    ("cr-cryptoslate", "https://cryptoslate.com/feed/", "CryptoSlate", "cryptoslate", "en", True),
    ("cr-cryptobriefing", "https://cryptobriefing.com/feed/", "Crypto Briefing", "cryptobriefing", "en", True),
    ("cr-beincrypto-es", "https://es.beincrypto.com/feed/", "BeInCrypto", "beincrypto", "es", True),
    ("cr-criptonoticias", "https://www.criptonoticias.com/feed/", "CriptoNoticias", "criptonoticias", "es", True),
    ("cr-diariobitcoin", "https://www.diariobitcoin.com/feed/", "DiarioBitcoin", "diariobitcoin", "es", True),
    ("cr-bbg-crypto", "https://feeds.bloomberg.com/crypto/news.rss", "Bloomberg", "bloomberg", "en", True),
    ("cr-bbg-tech", "https://feeds.bloomberg.com/technology/news.rss", "Bloomberg", "bloomberg", "en", False),
    ("cr-ft-crypto", "https://www.ft.com/cryptocurrencies?format=rss", "Financial Times", "ft", "en", True),
    ("cr-cnbc-crypto", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", "CNBC", "cnbc", "en", False),
    ("cr-guardian-crypto", "https://www.theguardian.com/technology/cryptocurrencies/rss", "The Guardian", "guardian", "en", True),
    ("cr-expansion-cripto", "https://e00-expansion.uecdn.es/rss/mercados/criptomonedas.xml", "Expansión", "unidad-editorial", "es", True),
    ("cr-investing-crypto", "https://www.investing.com/rss/news_301.rss", "Investing.com", "investing", "en", True),
    ("cr-fortune", "https://fortune.com/feed/fortune-feeds/?id=3230629", "Fortune", "fortune", "en", False),
    ("cr-marketwatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "MarketWatch", "dowjones", "en", False),
    ("cr-axios", "https://api.axios.com/feed/", "Axios", "axios", "en", False),
    ("cr-nyt-tech", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "The New York Times", "nyt", "en", False),
    ("cr-bbc-tech", "https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC", "bbc", "en", False),
    # ---- nuevos directos
    ("cr-btcmag", "https://bitcoinmagazine.com/feed", "Bitcoin Magazine", "btcmag", "en", True),
    ("cr-beincrypto", "https://beincrypto.com/feed/", "BeInCrypto", "beincrypto", "en", True),
    ("cr-cryptonews", "https://cryptonews.com/news/feed/", "Cryptonews", "cryptonews", "en", True),
    ("cr-utoday", "https://u.today/rss", "U.Today", "utoday", "en", True),
    ("cr-coingape", "https://coingape.com/feed/", "CoinGape", "coingape", "en", True),
    ("cr-newsbtc", "https://www.newsbtc.com/feed/", "NewsBTC", "newsbtc", "en", True),
    # ---- Google Noticias por sitio (medios sin RSS de cripto o bloqueados); "when:2d" va primero
    ("crq-reuters", "gn:site:reuters.com (bitcoin OR crypto OR stablecoin OR ethereum OR blockchain)", "Reuters", "reuters", "en", False),
    ("crq-bloomberg", "gn:site:bloomberg.com (bitcoin OR crypto OR stablecoin OR ethereum)", "Bloomberg", "bloomberg", "en", False),
    ("crq-cnbc", "gn:site:cnbc.com (bitcoin OR crypto OR stablecoin OR ethereum)", "CNBC", "cnbc", "en", False),
    ("crq-wsj", "gn:site:wsj.com (bitcoin OR crypto OR stablecoin OR ethereum)", "The Wall Street Journal", "dowjones", "en", False),
    ("crq-fortune", "gn:site:fortune.com (bitcoin OR crypto OR stablecoin OR ethereum)", "Fortune", "fortune", "en", False),
    ("crq-axios", "gn:site:axios.com (bitcoin OR crypto OR stablecoin OR ethereum)", "Axios", "axios", "en", False),
    ("crq-forbes", "gn:site:forbes.com (bitcoin OR crypto OR stablecoin OR ethereum)", "Forbes", "forbes", "en", False),
    ("crq-yahoo", "gn:site:finance.yahoo.com (bitcoin OR crypto OR stablecoin OR ethereum)", "Yahoo Finanzas", "yahoo", "en", False),
    ("crq-theblock", "gn:site:theblock.co", "The Block", "theblock", "en", True),
    ("crq-btcmag", "gn:site:bitcoinmagazine.com", "Bitcoin Magazine", "btcmag", "en", True),
    ("crq-infobae", "gn:site:infobae.com (bitcoin OR cripto OR criptomonedas OR stablecoin)", "Infobae", "infobae", "es", False),
    ("crq-eleconomista", "gn:site:eleconomista.com.mx (bitcoin OR cripto OR criptomonedas OR stablecoin)", "El Economista", "eleconomista", "es", False),
    ("crq-expansion", "gn:site:expansion.com (bitcoin OR cripto OR criptomonedas OR stablecoin)", "Expansión", "unidad-editorial", "es", False),
]

# Medios que se muestran como fuentes extra pero NO cuentan para los 5 medios:
# mucho contenido patrocinado, de precio o reescrito de otros medios.
LOW_TIER = {"beincrypto", "cryptonews", "utoday", "coingape", "newsbtc", "bitcoinist", "investing", "yahoo", "forbes"}
# Agregadores que republican notas de otros medios (Yahoo copia a Bloomberg o Decrypt tal cual): nunca cuentan.
AGGREGATORS = {"yahoo", "investing"}
MIN_REPUTABLE = 2   # los medios de LOW_TIER (salvo agregadores) solo suman si ya hay 2+ confiables
TIER_MODE = "hybrid"  # "strict": solo confiables; "hybrid": regla de arriba; "all": todos cuentan igual


def counted(orgs):
    good = orgs - LOW_TIER
    if TIER_MODE == "all":
        return set(orgs), good
    if TIER_MODE == "hybrid" and len(good) >= MIN_REPUTABLE:
        return orgs - AGGREGATORS, good
    return good, good

GNEWS = {"en": "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en",
         "es": "https://news.google.com/rss/search?q={}&hl=es-419&gl=US&ceid=US:es-419"}
GN_SUFFIX = re.compile(r"\s+[-|–]\s+[^-|–]{2,45}$")


def fetch(feed):
    fid, url, source, org, lang, dedicated = feed
    if not url.startswith("gn:"):
        return A.fetch_feed(feed)
    real = GNEWS[lang].format(quote("when:2d " + url[3:]))
    _, rows, err = A.fetch_feed((fid, real) + feed[2:])
    # Titular sin " - Medio"; el resumen de Google es solo el enlace, así que se descarta.
    return feed, [(GN_SUFFIX.sub("", t), l, d, "") for t, l, d, _ in rows or []] or None, err

CRYPTO_KNOWN_FAILS = [
    ("cointelegraph-es", "https://es.cointelegraph.com/rss", "410 Gone"),
    ("forbes-digital-assets", "https://www.forbes.com/digital-assets/feed/", "404"),
    ("yahoo-finance-crypto", "https://finance.yahoo.com/rss/topic/crypto", "404"),
    ("elpais-criptomonedas", "https://feeds.elpais.com/.../economia/criptomonedas/portada", "404"),
    ("infobae-criptomonedas", "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/criptomonedas/", "Feed vacío"),
    ("bitcoin-magazine", "https://bitcoinmagazine.com/.rss/full/", "403 / tiempo de espera"),
    ("reuters", "https://www.reuters.com/arc/outboundfeeds/rss/", "Reuters no ofrece RSS público (404)"),
    ("blockworks", "https://blockworks.co/feed", "Congelado (enero 2026)"),
    ("dlnews", "https://www.dlnews.com/arc/outboundfeeds/rss/", "Congelado (mayo 2026)"),
    ("forbes/fortune/wired/thestreet crypto", "-", "Sin RSS de cripto (404)"),
    ("eleconomista-cripto / benzinga-crypto", "-", "403"),
    ("dailyhodl / coinjournal / bitcoin.com", "-", "Excluidos a propósito: mucho contenido patrocinado"),
    ("bitcoinist", "https://bitcoinist.com/feed/", "Feed casi parado (última nota hace días)"),
    ("messari", "https://messari.io/rss", "404; en Google Noticias solo sale la portada"),
    ("blockworks / dlnews (Google Noticias)", "-", "Sin resultados por sitio"),
    ("fortune/axios/forbes cripto directo", "-", "404 / 403 (se usan por Google Noticias)"),
    ("the-verge-crypto", "https://www.theverge.com/rss/crypto/index.xml", "Feed vacío"),
]

CRYPTO = re.compile(
    r"(bitcoin|\bbtc\b|ethereum|\bether\b|\beth\b|crypto|cripto|stablecoin|blockchain|cadena de bloques|"
    r"binance|coinbase|kraken|tether|\busdt\b|\busdc\b|circle internet|solana|\bxrp\b|ripple|dogecoin|"
    r"\bdefi\b|\bnfts?\b|tokeniz|microstrategy|saylor|\bgemini\b|\bftx\b|\bcbdc\b|digital assets?|"
    r"activos digitales|\bmstr\b|hyperliquid|polymarket|kalshi|\bweb3\b|satoshi|altcoin|memecoin|"
    r"spot etf|\bdat\b|digital asset treasur|monedas? digital|euro digital|digital (euro|pound|dollar))",
    re.I,
)
# Comunicados, patrocinados, predicciones de precio, listas de compra, airdrops/promoción.
CRYPTO_SKIP = re.compile(
    r"(price prediction|predicci[oó]n de precio|price analysis|an[aá]lisis (de|del) precio|technical analysis|"
    r"an[aá]lisis t[eé]cnico|live levels|\btop \d+ (coins|cryptos?|altcoins|tokens)|best (crypto|coins|altcoins)|"
    r"(coins?|cryptos?|tokens?|altcoins?) to buy|comprar (ahora|hoy)|qu[eé] cripto comprar|airdrop|presale|"
    r"pre-?sale|preventa|sponsored|patrocinad|press release|comunicado de prensa|partner content|\[pr\]|"
    r"(could|may|will|to) (hit|reach|soar|explode|surge to|rally to) \$|price (could|may|will)|"
    r"\d+x (gains|potential)|100x|1000x|next (bitcoin|100x)|giveaway|sorteo|promo code|bonus code|"
    r"crypto (casino|gambling)|^daily (debrief|recap)|newsletter|podcast|^watch|^video|^opinion|"
    r"^opini[oó]n|^el (resumen|bolet[ií]n)|"
    r"price (outlook|forecast|target)s?\b(?! hike)|price could|(eyes|targets|eyeing) (\$|new high)|"
    r"(support|resistance) (level|zone)|\b(soporte|resistencia)\b|breakout|bull flag|bear flag|death cross|golden cross|"
    r"rally pattern|could (surge|soar|rally|pump|explode|crash|plunge|dump|drop|fall|rise) \d|"
    r"(a|para) observar|to watch (this|next)|(altcoins?|coins?|tokens?) to watch|\bshould you buy\b|"
    r"(google )?searches (drop|surge|spike)|\bwhales? (are )?(buy|sell|accumulat)|"
    r"(analyst|trader|expert)s? (says?|predicts?|warns?)|millionaire|\bmoon(ing|s)?\b|"
    r"\bprice today\b|current price of|precio (de hoy|hoy)|how high (will|can)|quote & history|forum & discussion|"
    r"what comes next|could reach|has (bitcoin|btc|ether\w*|eth|xrp) bottomed|we asked (claude|chatgpt|grok|gemini|ai)|"
    r"bull run|bullish (message|signal|setup)|crypto weekly|is an? (rebound|rally|breakout|recovery) .*likely|"
    r"can (bitcoin|btc|ether\w*|eth|xrp|solana)( price)? (defend|hold|reclaim|break|recover)|\bin focus\b|"
    r"valor de las principales (divisas|criptomonedas)|cotizaci[oó]n (de|del) (hoy|bitcoin))",
    re.I,
)
BLOCKED_DOMAINS = ("prnewswire.com", "globenewswire.com", "businesswire.com", "accesswire.com",
                   "newsfilecorp.com", "einpresswire.com", "chainwire.org")
BLOCKED_PATH = re.compile(r"/(sponsored|press-releases?|pr|partner-content|promoted|brandvoice|price-predictions?|"
                          r"price-analysis|learn|guides?|how-to)(/|$)", re.I)


def is_crypto(title: str, summary: str, dedicated: bool) -> bool:
    if CRYPTO.search(title):
        return True
    return dedicated and bool(CRYPTO.search(summary[:200]))


MERGE_COS = 0.42          # similitud mínima entre los "centros" de dos grupos
MERGE_COS_MANY = 0.35
MERGE_HOURS = 48


def merge_split(groups, pool, idf, n_ref):
    """Segunda pasada: une grupos que cuentan el mismo hecho con palabras distintas
    (p. ej. «OpenAI agent goes rogue» y «OpenAI model used testnet wallet»). Exige centros
    parecidos y 2+ términos poco comunes que aparezcan en titulares de los dos grupos."""
    import math
    rare_cut = math.log((n_ref + 1) / (max(4, n_ref * 0.012) + 0.5))

    def centre(g):
        c = Counter()
        for i in g:
            for w, v in pool[i]["_vec"].items():
                c[w] += v
        n = math.sqrt(sum(v * v for v in c.values())) or 1.0
        return {w: v / n for w, v in c.items()}

    def title_rare(g):
        return {w for i in g for w in pool[i]["_tt"] if idf.get(w, 0) >= rare_cut}

    changed = True
    while changed:
        changed = False
        info = [(centre(g), title_rare(g), min(pool[i]["_ts"] for i in g), max(pool[i]["_ts"] for i in g)) for g in groups]
        best = None
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                if len(groups[a]) + len(groups[b]) < 3:
                    continue          # dos notas sueltas ya las juzgó el agrupador normal
                if max(info[a][3], info[b][3]) - min(info[a][2], info[b][2]) > MERGE_HOURS * 3600:
                    continue
                shared = len(info[a][1] & info[b][1])
                if shared < 2:
                    continue
                c = A.cos(info[a][0], info[b][0])
                # Con 4+ términos raros en común en los titulares basta un centro algo menos parecido.
                need = MERGE_COS if shared < 4 else MERGE_COS_MANY
                if c >= need and (best is None or c > best[0]):
                    best = (c, a, b)
        if best:
            _, a, b = best
            groups[a] = groups[a] + groups[b]
            del groups[b]
            changed = True
    return groups


def prefer_reputable(st, members):
    """Titular y resumen de un medio que cuenta para el consenso, no de uno de los extra."""
    low_src = {m["source"] for m in members if m["org"] in LOW_TIER}
    good = [m for m in sorted(members, key=lambda m: m["_ts"]) if m["org"] not in LOW_TIER]
    for lang, hk in (("es", "headlineEs"), ("en", "headlineEn")):
        cur = next((m for m in members if m["title"] == st.get(hk)), None)
        if cur and cur["org"] in LOW_TIER:
            alt = next((m for m in good if m["lang"] == lang), None)
            st[hk] = alt["title"] if alt else st[hk]
        sk, ss = "summary" + lang.capitalize(), "summary" + lang.capitalize() + "Source"
        if st.get(ss) in low_src:
            alt = next((m for m in good if m["lang"] == lang and len(m["summary"]) >= 60), None)
            st[sk], st[ss] = (alt["summary"], alt["source"]) if alt else (st[sk], st[ss])
    st["headline"] = st["headlineEs"] or st["headlineEn"]


def build(now, general_pool):
    """Devuelve (historias, informe). general_pool = notas ya limpiadas por actualizar.py."""
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(fetch, CRYPTO_FEEDS))

    pool, seen = [], set()
    candidates = []  # grupos de 2 medios para "Posibles noticias"
    feeds_ok, feeds_failed, rejected = [], [], Counter()

    def add(it):
        key = (urlparse(it["url"]).netloc.replace("www.", "") + urlparse(it["url"]).path.rstrip("/")).lower()
        tkey = it["org"] + "|" + re.sub(r"\W+", "", A.fold(it["title"].lower()))[:90]
        if key in seen or tkey in seen:
            return False
        seen.add(key)
        seen.add(tkey)
        pool.append(it)
        return True

    def ok_item(title, url, summary):
        d = urlparse(url).netloc.lower()
        if any(d.endswith(b) for b in BLOCKED_DOMAINS):
            rejected["comunicado"] += 1
            return False
        if BLOCKED_PATH.search(urlparse(url).path) or A.SKIP_PATH.search(urlparse(url).path.lower()):
            rejected["sección no noticiosa"] += 1
            return False
        if CRYPTO_SKIP.search(title) or A.SKIP_TITLE.search(title):
            rejected["predicción/promo/formato"] += 1
            return False
        if re.search(r"sponsored|patrocinado|press release|this is a paid", summary[:300], re.I):
            rejected["patrocinado"] += 1
            return False
        return True

    for feed, rows, err in results:
        fid, url, source, org, lang, dedicated = feed
        if err or not rows:
            feeds_failed.append({"id": fid, "source": source, "url": url, "error": err or "sin ítems"})
            continue
        kept = 0
        for title, link, date_s, desc in rows:
            if len(title) < 18:
                continue
            u = A.clean_url(link)
            if not u.startswith("http"):
                continue
            pub = A.parse_date(date_s)
            if pub is None or pub > now + timedelta(hours=3) or pub < now - timedelta(hours=A.NEWS_HOURS):
                continue
            summary = desc if desc and A.fold(desc.lower())[:60] != A.fold(title.lower())[:60] else ""
            if not is_crypto(title, summary, dedicated):
                continue
            if not ok_item(title, u, summary):
                continue
            if add({"title": title, "url": u, "source": source, "org": org, "lang": lang,
                    "summary": A.trim(summary), "category": "cripto", "feed": fid,
                    "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "_ts": pub.timestamp()}):
                kept += 1
        feeds_ok.append({"id": fid, "source": source, "url": url, "itemsInFeed": len(rows), "kept": kept})

    from_general = 0
    for it in general_pool:
        if not CRYPTO.search(it["title"]):
            continue
        if not ok_item(it["title"], it["url"], it["summary"]):
            continue
        if add({k: it[k] for k in ("title", "url", "source", "org", "lang", "summary", "feed", "publishedAt", "_ts")}
               | {"category": "cripto"}):
            from_general += 1

    stories, debug = [], []
    groups = []
    if len(pool) > 1:
        # La rareza de un término se mide contra todo el corpus del día (notas generales + cripto);
        # si solo se usara el corpus cripto, nombres como "Kraken" o "Payward" parecerían comunes.
        crypto_urls = {it["url"] for it in pool}
        background = [{k: it[k] for k in ("title", "summary", "lang", "_ts")}
                      for it in general_pool if it["url"] not in crypto_urls]
        idf, df = A.build_vectors(pool + background)
        groups, sims = A.cluster(pool, idf, df, n_ref=len(pool) + len(background))
        groups = merge_split(groups, pool, idf, len(pool) + len(background))
        for g in groups:
            members = [pool[i] for i in g]
            orgs = {m["org"] for m in members}
            cnt, good = counted(orgs)         # medios que cuentan para el consenso
            if len(orgs) >= 2:
                debug.append((len(cnt), members))
            if len(good) < 2:
                continue
            st = A.make_story(g, pool, sims)
            prefer_reputable(st, members)
            st["outlets"] = len(cnt)
            st["extraOutlets"] = len(orgs) - len(cnt)
            if len(cnt) < MIN_OUTLETS:
                candidates.append(st)
                continue
            stories.append(st)
    stories.sort(key=lambda s: (s["outlets"], s["_last"]), reverse=True)
    stories = stories[:MAX_STORIES]
    for i, s in enumerate(stories):
        s.pop("_last", None)
        s["id"] = f"cripto-{i + 1}"

    org_counts = Counter(len(counted({pool[i]["org"] for i in g})[0]) for g in groups)
    report = {
        "_candidates": candidates,
        "minOutlets": MIN_OUTLETS,
        "feedsOk": feeds_ok, "feedsFailed": feeds_failed,
        "knownFails": [{"id": a, "url": b, "error": c} for a, b, c in CRYPTO_KNOWN_FAILS],
        "itemsGathered": len(pool), "fromGeneralFeeds": from_general, "rejected": dict(rejected),
        "clusters": len(groups),
        "groupsByOutletCount": {str(k): v for k, v in sorted(org_counts.items())},
        "stories": len(stories),
    }
    return stories, report, debug
