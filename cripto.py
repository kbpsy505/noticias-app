"""Pestaña "Criptomonedas": consenso estricto, solo con código.

Una historia aparece solo si la publican 5 o más medios distintos (misma regla de
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
from urllib.parse import urlparse

import actualizar as A

MIN_OUTLETS = 5
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
]

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
    ("cryptonews / dailyhodl / coinjournal / newsbtc / bitcoinist / bitcoin.com",
     "-", "Excluidos a propósito: mucho contenido patrocinado o de baja fiabilidad"),
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
    r"^opini[oó]n|^el (resumen|bolet[ií]n))",
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


def build(now, general_pool):
    """Devuelve (historias, informe). general_pool = notas ya limpiadas por actualizar.py."""
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(A.fetch_feed, CRYPTO_FEEDS))

    pool, seen = [], set()
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
        for g in groups:
            members = [pool[i] for i in g]
            orgs = {m["org"] for m in members}
            if len(orgs) >= 2:
                debug.append((len(orgs), members))
            if len(orgs) < MIN_OUTLETS:
                continue
            stories.append(A.make_story(g, pool, sims))
    stories.sort(key=lambda s: (s["outlets"], s["_last"]), reverse=True)
    stories = stories[:MAX_STORIES]
    for i, s in enumerate(stories):
        s.pop("_last", None)
        s["id"] = f"cripto-{i + 1}"

    org_counts = Counter(len({pool[i]["org"] for i in g}) for g in groups)
    report = {
        "minOutlets": MIN_OUTLETS,
        "feedsOk": feeds_ok, "feedsFailed": feeds_failed,
        "knownFails": [{"id": a, "url": b, "error": c} for a, b, c in CRYPTO_KNOWN_FAILS],
        "itemsGathered": len(pool), "fromGeneralFeeds": from_general, "rejected": dict(rejected),
        "clusters": len(groups),
        "groupsByOutletCount": {str(k): v for k, v in sorted(org_counts.items())},
        "stories": len(stories),
    }
    return stories, report, debug
