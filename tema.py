"""Refuerzo de las pestañas "Mundo de finanzas" y "Ciencias" (misma idea que cripto.py).

Para cada tema se suman medios especializados (RSS directo o búsqueda de Google Noticias por
sitio) a las notas del tema que ya trae el corpus general, y se agrupa aparte. La regla no
cambia: una historia aparece solo si la publican 5 o más medios distintos.
- Medios de baja fiabilidad o que reescriben comunicados (LOW) solo suman cuando la historia ya
  tiene 3+ medios confiables; los agregadores que republican notas ajenas (AGG) nunca cuentan.
- Se descartan comunicados, patrocinados, consejos de finanzas personales, recomendaciones de
  acciones, ofertas y notas de servicio.
- Una segunda pasada une grupos que cuentan el mismo hecho con palabras distintas.
No inventa nada: titulares y resúmenes salen tal cual de cada medio.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import quote, urlparse

import actualizar as A

MIN_OUTLETS = 5
MIN_RELIABLE = 3
GNEWS = {"en": "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en",
         "es": "https://news.google.com/rss/search?q={}&hl=es-419&gl=US&ceid=US:es-419"}
GN_SUFFIX = re.compile(r"\s+[-|–]\s+[^-|–]{2,45}$")
PR_DOMAINS = ("prnewswire.com", "globenewswire.com", "businesswire.com", "accesswire.com", "newsfilecorp.com",
              "einpresswire.com", "eurekalert.org")
PR_PATH = re.compile(r"/(sponsored|press-releases?|partner-content|promoted|brandvoice|deals?|shopping|coupons?|"
                     r"personal-finance|retirement|credit-cards?|mortgages?|reviews?|best-|buying-guide|newsletters?)(/|$)", re.I)

# (id, url o "gn:consulta", medio, organización, idioma, dedicado)
# dedicado=True: todo lo del feed es del tema; False: el titular debe nombrar el tema.
TOPICS = {
    "finanzas": {
        "label": "Mundo de finanzas", "hours": A.NEWS_HOURS, "gn_when": "2d", "merge_hours": 48,
        "match": A.FINANZAS,
        "feeds": [
            ("fin-cnbc-markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069", "CNBC", "cnbc", "en", True),
            ("fin-cnbc-econ", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "CNBC", "cnbc", "en", True),
            ("fin-mw", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "MarketWatch", "dowjones", "en", False),
            ("fin-wsj", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain", "The Wall Street Journal", "dowjones", "en", True),
            ("fin-fortune", "https://fortune.com/feed/fortune-feeds/?id=3230629", "Fortune", "fortune", "en", False),
            ("fin-bi", "https://feeds.businessinsider.com/custom/all", "Business Insider", "businessinsider", "en", False),
            ("fin-axios", "https://api.axios.com/feed/", "Axios", "axios", "en", False),
            ("fin-bbg-biz", "https://feeds.bloomberg.com/business/news.rss", "Bloomberg", "bloomberg", "en", True),
            ("fin-ft-eco", "https://www.ft.com/global-economy?format=rss", "Financial Times", "ft", "en", True),
            ("fin-ft-companies", "https://www.ft.com/companies?format=rss", "Financial Times", "ft", "en", True),
            ("fin-cincodias", "https://feeds.elpais.com/mrss-s/pages/ep/site/cincodias.elpais.com/portada", "Cinco Días", "elpais", "es", True),
            ("fin-bbglinea", "https://www.bloomberglinea.com/arc/outboundfeeds/rss/?outputType=xml", "Bloomberg Línea", "bloomberglinea", "es", True),
            ("finq-reuters-biz", "gn:site:reuters.com/business", "Reuters", "reuters", "en", False),
            ("finq-reuters-markets", "gn:site:reuters.com/markets", "Reuters", "reuters", "en", True),
            ("finq-ap", "gn:site:apnews.com (economy OR stocks OR markets OR inflation OR tariffs OR fed)", "AP", "ap", "en", False),
            ("finq-wsj", "gn:site:wsj.com (markets OR economy OR stocks OR fed)", "The Wall Street Journal", "dowjones", "en", False),
            ("finq-barrons", "gn:site:barrons.com", "Barron's", "barrons", "en", True),
            ("finq-nikkei", "gn:site:asia.nikkei.com", "Nikkei Asia", "nikkei", "en", False),
            ("finq-yahoo", "gn:site:finance.yahoo.com (stocks OR economy OR fed OR earnings OR markets)", "Yahoo Finanzas", "yahoo", "en", False),
            ("finq-eleconomista", "gn:site:eleconomista.com.mx (economía OR mercados OR peso OR Banxico OR inflación)", "El Economista", "eleconomista", "es", False),
            ("finq-larepublica", "gn:site:larepublica.net (economía OR dólar OR BCCR OR exportaciones OR inflación OR empresas)", "La República (CR)", "larepublica-cr", "es", False),
            ("fin-cnbc-world", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "CNBC", "cnbc", "en", True),
            ("fin-nyt-economy", "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml", "The New York Times", "nyt", "en", True),
            ("fin-guardian-eco", "https://www.theguardian.com/business/economics/rss", "The Guardian", "guardian", "en", True),
            ("finq-elfinanciero", "gn:site:elfinancierocr.com", "El Financiero (Costa Rica)", "grupo-nacion", "es", True),
        ],
        "low": {"businessinsider", "fortune", "barrons"},
        "agg": {"yahoo"},
        "skip": re.compile(
            r"(?i)(\b(stocks?|acciones) to (buy|watch|sell)\b|\bbest (stocks?|etfs?|funds?|credit cards?|savings|cd rates)\b|"
            r"\bshould you (buy|sell)\b|poised for a breakout|\bmy (husband|wife|daughter|son|dad|mom|friends?|boss|parents)\b|"
            r"^(i|we|my) |\bi'm\b|\bi (was|am|have|had|went|bought|sold|quit|retired|make|earn)\b|retire(ment)? (at|early|on)|"
            r"social security (check|payment)|mortgage rates? today|cd rates|savings rates?|how to (save|invest|retire|buy)|"
            r"\bwhy .{1,40} stock is (falling|rising|soaring|sinking|down|up) today\b|stock (market )?today:|live updates?|"
            r"dow jones today|futures:|premarket|pre-market|\btop movers\b|stocks making the biggest moves|"
            r"\bsponsored\b|\bpatrocinad|press release|comunicado de prensa|announces .{0,40}(private placement|offering)|"
            r"\bquiz\b|podcast|newsletter|^watch|^video|opinion|opini[oó]n|^cartas?\b|"
            r"\((tsx|lse|nyse|nasdaq|asx|nyseamerican):|\b[A-Z]{1,5}\) stock\b|stocks? (set|poised|ready) to|stock may be|"
            r"buying opportunit|favou?rite (wall street )?stocks|worth your attention|chart of the week|midday|"
            r"stock market (today|midday|news)|earnings preview|fully priced|can defy|\bstocks? (that|we) |"
            r"\b\d+ [\w\s-]{0,25}(stocks|etfs|reasons|things|picks)\b|is it time to|what to expect|week ahead|\bmorning bid\b|"
            r"(gold|oil|silver|futures|yields?|dollar) (edge|edges|inch|inches|tick|ticks)\b)"),
    },
    "ciencias": {
        "label": "Ciencias", "hours": A.SCIENCE_HOURS, "gn_when": "7d", "merge_hours": 96, "anchor_hours": 72,
        "match": A.SCIENCE,
        "feeds": [
            ("sci-sciam", "https://www.scientificamerican.com/platform/syndication/rss/", "Scientific American", "sciam", "en", True),
            ("sci-sciencedaily", "https://www.sciencedaily.com/rss/top/science.xml", "ScienceDaily", "sciencedaily", "en", True),
            ("sci-physorg", "https://phys.org/rss-feed/", "Phys.org", "physorg", "en", True),
            ("sci-nasa", "https://www.nasa.gov/news-release/feed/", "NASA", "nasa", "en", True),
            ("sci-esa", "https://www.esa.int/rssfeed/Our_Activities/Space_News", "ESA", "esa", "en", True),
            ("sci-smithsonian", "https://www.smithsonianmag.com/rss/science-nature/", "Smithsonian", "smithsonian", "en", True),
            ("sci-quanta", "https://api.quantamagazine.org/feed/", "Quanta", "quanta", "en", True),
            ("sci-ars", "https://feeds.arstechnica.com/arstechnica/science", "Ars Technica", "ars", "en", True),
            ("sci-conversation", "https://theconversation.com/global/articles.atom", "The Conversation", "conversation", "en", False),
            ("sci-conversation-es", "https://theconversation.com/es/articles.atom", "The Conversation", "conversation", "es", False),
            ("sci-sciencenews", "https://www.sciencenews.org/feed", "Science News", "sciencenews", "en", True),
            ("sci-nyt-space", "https://rss.nytimes.com/services/xml/rss/nyt/Space.xml", "The New York Times", "nyt", "en", True),
            ("sci-muyinteresante", "https://www.muyinteresante.com/feed", "Muy Interesante", "muyinteresante", "es", False),
            ("sci-livescience", "https://www.livescience.com/feeds/all", "Live Science", "livescience", "en", True),
            ("sci-space", "https://www.space.com/feeds/all", "Space.com", "spacecom", "en", True),
            ("sci-wired", "https://www.wired.com/feed/category/science/latest/rss", "Wired", "wired", "en", False),
            ("sci-popsci", "https://www.popsci.com/feed/", "Popular Science", "popsci", "en", False),
            ("sci-sciencealert", "https://www.sciencealert.com/feed", "ScienceAlert", "sciencealert", "en", True),
            ("sci-universetoday", "https://www.universetoday.com/feed/", "Universe Today", "universetoday", "en", True),
            ("sciq-reuters", "gn:site:reuters.com/science", "Reuters", "reuters", "en", True),
            ("sciq-ap", "gn:site:apnews.com (science OR scientists OR space OR NASA OR study OR researchers)", "AP", "ap", "en", False),
            ("sciq-cnn", "gn:site:cnn.com/science", "CNN", "cnn", "en", True),
            ("sciq-newscientist", "gn:site:newscientist.com", "New Scientist", "newscientist", "en", True),
            ("sciq-natgeo", "gn:site:nationalgeographic.com (science OR animals OR space OR scientists OR discovery)", "National Geographic", "natgeo", "en", False),
            ("sciq-livescience", "gn:site:livescience.com", "Live Science", "livescience", "en", True),
            ("sciq-space", "gn:site:space.com", "Space.com", "spacecom", "en", True),
            ("sciq-sinc", "gn:site:agenciasinc.es", "SINC", "sinc", "es", True),
            ("sciq-natgeo-es", "gn:site:nationalgeographic.com.es", "National Geographic España", "natgeo", "es", False),
            ("sciq-infobae", "gn:site:infobae.com/ciencia OR site:infobae.com (científicos OR estudio OR NASA OR espacio)", "Infobae", "infobae", "es", False),
        ],
        # Republican comunicados de universidades o son fuente primaria (no medio): solo suman con 3+ confiables.
        "low": {"sciencedaily", "physorg", "nasa", "esa", "muyinteresante", "spacecom", "livescience",
                "sciencealert", "universetoday"},
        "agg": set(),
        "skip": re.compile(
            r"(?i)(\bdeals?\b|\boferta|\bdescuento|\bprecio\b|black friday|smart tv|\bsale\b|\bbuy\b|\bcomprar\b|"
            r"\breview\b|best (telescope|binoculars|camera)|how to (watch|see)|\bquiz\b|crossword|wordle|"
            r"night sky|qué ver en el cielo|horóscopo|hor[oó]scopo|apod:|picture of the day|podcast|newsletter|"
            r"^watch|^video|opinion|opini[oó]n|briefing chat|author at|page \d+ of \d+|^last word|this week.s new questions|\bsponsored\b|patrocinad|press release|comunicado de prensa)"),
    },
}


# Notas de mercado que mencionan una guerra (p. ej. «el petróleo sube por Oriente Medio») sí son de finanzas.
MARKET = re.compile(r"(?i)\b(oil prices?|crude|brent|petr[oó]leo|stocks?|shares|markets?|mercados?|bolsas?|bonds?|bonos|"
                    r"yields?|inflation|inflaci[oó]n|currency|divisas?|gold prices?|precio del oro|\$\d+ a barrel|barril)\b")


def fetch(args):
    feed, when = args
    fid, url, source, org, lang, dedicated = feed
    if not url.startswith("gn:"):
        return A.fetch_feed(feed)
    real = GNEWS[lang].format(quote(f"when:{when} " + url[3:]))
    _, rows, err = A.fetch_feed((fid, real) + feed[2:])
    return feed, [(GN_SUFFIX.sub("", t), l, d, "") for t, l, d, _ in rows or []] or None, err


def counted(orgs, low, agg):
    good = orgs - low - agg
    if len(good) >= MIN_RELIABLE:
        return orgs - agg, good
    return good, good


def proper(title):
    """Nombres propios del titular (palabras con mayúscula que no abren la frase)."""
    words = re.findall(r"[\w’']+", title)
    out = set()
    for i, w in enumerate(words):
        if i and len(w) >= 4 and w[0].isupper() and not w.isupper() and not words[i - 1].endswith(":"):
            k = A.fold(w.lower()).replace("’s", "").replace("'s", "")
            if k not in ANCHOR_STOP:
                out.update(A.terms(k))     # misma forma que los términos del agrupador
    return out


ANCHOR_COS = 0.30
ANCHOR_STOP = set("wall street stocks stock markets market growth high record federal reserve treasury treasurys bonds "
                  "earnings shares prices price investors analysis chart week today news report study scientists "
                  "researchers january february march april june july august september october november december "
                  "monday tuesday wednesday thursday friday saturday sunday lunes martes miercoles jueves viernes sabado domingo "
                  "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre "
                  "bolsa estados unidos gobierno banco central".split())      # mismo nombre propio poco común + centros algo parecidos
ANCHOR_HOURS = 30


def merge_split(groups, pool, idf, n_ref, hours, cos_min=0.42, cos_many=0.35, anchor_h=ANCHOR_HOURS, cross=False, anchor_extra=0.0, anchor_cos=None, cos_strong=None):
    """Une grupos del mismo hecho contado con palabras distintas: centros parecidos y 2+ términos
    poco comunes en los titulares de ambos (4+ términos permiten un centro algo menos parecido)."""
    rare_cut = math.log((n_ref + 1) / (max(4, n_ref * 0.012) + 0.5))

    def centre(g):
        c = Counter()
        for i in g:
            for w, v in pool[i]["_vec"].items():
                c[w] += v
        n = math.sqrt(sum(v * v for v in c.values())) or 1.0
        return {w: v / n for w, v in c.items()}

    merges = []
    while True:
        info = [(centre(g), {w for i in g for w in pool[i]["_tt"] if idf.get(w, 0) >= rare_cut},
                 min(pool[i]["_ts"] for i in g), max(pool[i]["_ts"] for i in g),
                 {w for i in g for w in proper(pool[i]["title"]) if idf.get(w, 0) >= rare_cut + anchor_extra}) for g in groups]
        best = None
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                span = max(info[a][3], info[b][3]) - min(info[a][2], info[b][2])
                if span > hours * 3600:
                    continue
                shared = len(info[a][1] & info[b][1])
                # Nombre propio de un grupo que también aparece (como término raro) en los titulares del otro.
                if cross:
                    anchor = bool((info[a][4] & info[b][1]) or (info[b][4] & info[a][1]))
                else:
                    anchor = bool(info[a][4] & info[b][4])
                anchor = anchor and span <= anchor_h * 3600
                # Historia muy grande: sus palabras dejan de ser «raras» en el conjunto; con un centro muy
                # parecido (cos_strong) se unen igual aunque no compartan términos raros.
                strong = cos_strong is not None and len(groups[a]) >= 3 and len(groups[b]) >= 3
                if shared < 2 and not anchor and not strong:
                    continue
                if len(groups[a]) + len(groups[b]) < 3 and not anchor:
                    continue
                c = A.cos(info[a][0], info[b][0])
                need = (anchor_cos or ANCHOR_COS) if anchor else (cos_min if shared < 4 else cos_many)
                if shared < 2 and not anchor:
                    need = cos_strong
                if c >= need and (best is None or c > best[0]):
                    best = (c, a, b, anchor, shared)
        if not best:
            return groups, merges
        c, a, b, anc, sh = best
        merges.append(([pool[i]["title"] for i in groups[a]][:2], [pool[i]["title"] for i in groups[b]][:2], round(c, 2), anc, sh))
        groups[a] = groups[a] + groups[b]
        del groups[b]


def prefer_reliable(st, members, low, agg):
    bad = low | agg
    low_src = {m["source"] for m in members if m["org"] in bad}
    good = [m for m in sorted(members, key=lambda m: m["_ts"]) if m["org"] not in bad]
    for lang, hk in (("es", "headlineEs"), ("en", "headlineEn")):
        cur = next((m for m in members if m["title"] == st.get(hk)), None)
        if cur and cur["org"] in bad:
            alt = next((m for m in good if m["lang"] == lang), None)
            if alt:
                st[hk] = alt["title"]
        sk, ss = "summary" + lang.capitalize(), "summary" + lang.capitalize() + "Source"
        if st.get(ss) in low_src:
            alt = next((m for m in good if m["lang"] == lang and len(m["summary"]) >= 60), None)
            if alt:
                st[sk], st[ss] = alt["summary"], alt["source"]
    st["headline"] = st["headlineEs"] or st["headlineEn"]


def build(cat, now, general_pool, main_feed_urls=()):
    cfg = TOPICS[cat]
    feeds = [f for f in cfg["feeds"] if f[1] not in main_feed_urls]
    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(fetch, [(f, cfg["gn_when"]) for f in feeds]))
    low, agg, skip, match = cfg["low"], cfg["agg"], cfg["skip"], cfg["match"]
    pool, seen, rejected = [], set(), Counter()
    feeds_ok, feeds_failed = [], []

    def add(it):
        p = urlparse(it["url"])
        key = (p.netloc.replace("www.", "") + p.path.rstrip("/")).lower()
        tkey = it["org"] + "|" + re.sub(r"\W+", "", A.fold(it["title"].lower()))[:90]
        if key in seen or tkey in seen:
            return False
        seen.update((key, tkey))
        pool.append(it)
        return True

    def ok(title, url, summary):
        p = urlparse(url)
        if any(p.netloc.lower().endswith(d) for d in PR_DOMAINS):
            rejected["comunicado"] += 1
            return False
        if PR_PATH.search(p.path) or A.SKIP_PATH.search(p.path.lower()):
            rejected["sección no noticiosa"] += 1
            return False
        if skip.search(title) or A.SKIP_TITLE.search(title):
            rejected["consejo/promo/formato"] += 1
            return False
        if re.search(r"sponsored|patrocinado|press release|this is a paid", summary[:300], re.I):
            rejected["patrocinado"] += 1
            return False
        return True

    from feeds import FEEDS
    hinted = {f[0] for f in FEEDS if f[5] == cat}
    for it in general_pool:          # lo que el corpus general ya clasificó en este tema
        if it.get("category") == cat and (it.get("feed") in hinted or match.search(it["title"] + ("" if cat == "ciencias" else " " + it["summary"][:200]))) \
                and not ((A.WAR.search(it["title"]) and not (cat == "finanzas" and MARKET.search(it["title"])))
                         or A.SUCESOS.search(it["title"])) and ok(it["title"], it["url"], it["summary"]):
            add({k: it[k] for k in ("title", "url", "source", "org", "lang", "summary", "feed", "publishedAt", "_ts")})
    from_general = len(pool)

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
            pub = A.parse_date(date_s)
            if not u.startswith("http") or pub is None or pub > now + timedelta(hours=3) or pub < now - timedelta(hours=cfg["hours"]):
                continue
            summary = desc if desc and A.fold(desc.lower())[:60] != A.fold(title.lower())[:60] else ""
            if (A.WAR.search(title) and not (cat == "finanzas" and MARKET.search(title))) or A.SUCESOS.search(title):
                rejected["guerra/suceso"] += 1
                continue
            if not (match.search(title) or (dedicated and match.search(summary[:200])) or (dedicated and cat == "ciencias")):
                continue
            if not ok(title, u, summary):
                continue
            if add({"title": title, "url": u, "source": source, "org": org, "lang": lang, "summary": A.trim(summary),
                    "feed": fid, "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "_ts": pub.timestamp()}):
                kept += 1
        feeds_ok.append({"id": fid, "source": source, "itemsInFeed": len(rows), "kept": kept})

    stories, candidates, debug, merges = [], [], [], []
    groups = []
    if len(pool) > 1:
        urls = {it["url"] for it in pool}
        background = [{k: it[k] for k in ("title", "summary", "lang", "_ts")} for it in general_pool if it["url"] not in urls]
        idf, df = A.build_vectors(pool + background)
        old = A.PAIR_WINDOW_H
        A.PAIR_WINDOW_H = max(old, 72 if cat == "ciencias" else old)   # la ciencia se publica en varios días
        try:
            groups, sims = A.cluster(pool, idf, df, n_ref=len(pool) + len(background))
        finally:
            A.PAIR_WINDOW_H = old
        groups, merges = merge_split(groups, pool, idf, len(pool) + len(background), cfg["merge_hours"],
                                     anchor_h=cfg.get("anchor_hours", ANCHOR_HOURS), cross=cat == "ciencias",
                                     anchor_extra=0.7 if cat == "ciencias" else 0.0)
        for g in groups:
            members = [pool[i] for i in g]
            orgs = {m["org"] for m in members}
            cnt, good = counted(orgs, low, agg)
            if len(orgs) >= 2:
                debug.append((len(cnt), members))
            if len(good) < 2:
                continue
            st = A.make_story(g, pool, sims)
            prefer_reliable(st, members, low, agg)
            st["outlets"] = len(cnt)
            st["extraOutlets"] = len(orgs) - len(cnt)
            st["category"] = cat
            (stories if len(cnt) >= MIN_OUTLETS else candidates).append(st)
    stories.sort(key=lambda s: (s["outlets"], s["_last"]), reverse=True)
    stories = stories[:A.MAX_STORIES]
    for s in stories:              # actualizar.py ordena, recorta y pone los ids
        s.pop("category", None)
    report = {
        "itemsGathered": len(pool), "fromGeneralFeeds": from_general, "rejected": dict(rejected),
        "feedsOk": feeds_ok, "feedsFailed": feeds_failed,
        "groupsByOutletCount": {str(k): v for k, v in sorted(Counter(len(counted({pool[i]["org"] for i in g}, low, agg)[0]) for g in groups).items())},
        "stories": len(stories), "candidates": len(candidates), "merges": len(merges),
    }
    return stories, candidates, report, debug, merges
