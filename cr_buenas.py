"""Fuentes ticas para Buenas noticias: medios, universidades y búsquedas de Google Noticias por sitio."""
import re, sys, subprocess, json
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import actualizar as A

GN = "https://news.google.com/rss/search?q=when:3d+site:{}&hl=es-419&gl=CR&ceid=CR:es-419"
# (id, url, fuente, org, lang, tipo)  tipo: medio | inst (institución: universidad, etc.)
CR_GOOD_FEEDS = [
    ("cr-nacion", "https://www.nacion.com/arc/outboundfeeds/rss/?outputType=xml", "La Nación (Costa Rica)", "grupo-nacion", "es", "medio"),
    ("cr-nacion-pais", "https://www.nacion.com/arc/outboundfeeds/rss/category/el-pais/?outputType=xml", "La Nación (Costa Rica)", "grupo-nacion", "es", "medio"),
    ("cr-nacion-viva", "https://www.nacion.com/arc/outboundfeeds/rss/category/viva/?outputType=xml", "La Nación (Costa Rica)", "grupo-nacion", "es", "medio"),
    ("cr-lateja", "https://www.lateja.cr/arc/outboundfeeds/rss/?outputType=xml", "La Teja", "grupo-nacion", "es", "medio"),
    ("cr-crhoy", "https://crhoy.com/sitemaps/sitemap-news.xml", "CRHoy", "crhoy", "es", "medio"),
    ("cr-teletica", GN.format("teletica.com"), "Teletica", "teletica", "es", "medio"),
    ("cr-repretel", GN.format("repretel.com"), "Repretel", "repretel", "es", "medio"),
    ("cr-ameliarueda", GN.format("ameliarueda.com"), "AmeliaRueda.com", "ameliarueda", "es", "medio"),
    ("cr-extra", "https://www.diarioextra.com/feed", "Diario Extra", "diarioextra", "es", "medio"),
    ("cr-delfino", "https://delfino.cr/feed", "Delfino", "delfino", "es", "medio"),
    ("cr-semanario", "https://semanariouniversidad.com/feed/", "Semanario Universidad", "semanario", "es", "medio"),
    ("cr-observador", "https://observador.cr/feed/", "El Observador", "observador", "es", "medio"),
    ("cr-trivision", "https://trivisioncr.com/news-sitemap.xml", "Trivisión", "trivision", "es", "medio"),
    ("cr-elmundo", "https://www.elmundo.cr/feed/", "El Mundo CR", "elmundo-cr", "es", "medio"),
    ("cr-amprensa", "https://amprensa.com/feed/", "AM Prensa", "amprensa", "es", "medio"),
    ("cr-monumental", "https://www.monumental.co.cr/feed/", "Monumental", "monumental", "es", "medio"),
    ("cr-ticotimes", "https://ticotimes.net/feed", "The Tico Times", "ticotimes", "en", "medio"),
    ("cr-crnews", "https://thecostaricanews.com/feed/", "The Costa Rica News", "crnews", "en", "medio"),
    ("cr-ucr", GN.format("ucr.ac.cr"), "UCR", "ucr", "es", "inst"),
    ("cr-tec", "https://www.tec.ac.cr/rss.xml", "TEC", "tec", "es", "inst"),
    ("cr-una", "https://www.unacomunica.una.ac.cr/index.php?format=feed&type=rss", "UNA Comunica", "una", "es", "inst"),
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SUFFIX = re.compile(r"\s+[|\-–]\s*(CR ?Hoy|Teletica|Repretel|Noticias Repretel|Diario Extra|Trivisi[oó]n[^|]*|AmeliaRueda\.com|"
                    r"Amelia Rueda|Universidad de Costa Rica|UCR|Tecnológico de Costa Rica|La Nación Costa Rica|La Nación|Delfino\.cr|Delfino|"
                    r"Semanario Universidad|El Mundo CR|AM Prensa|El Observador( CR)?|Monumental|elmundo\.cr|Teletica\.com)\s*$", re.I)


def fetch(feed):
    fid, url = feed[0], feed[1]
    try:
        return feed, A.parse_items(A.fetch(url)), None
    except Exception as exc:
        try:  # p. ej. Tico Times responde comprimido en brotli
            data = subprocess.run(["curl", "-sL", "-m", "25", "--compressed", "-A", UA, url], capture_output=True).stdout
            return feed, A.parse_items(data.lstrip()), None
        except Exception as exc2:
            return feed, None, f"{type(exc).__name__} / {type(exc2).__name__}"


def gather(now, hours=72):
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(fetch, CR_GOOD_FEEDS))
    items, seen, status = [], set(), []
    for feed, rows, err in res:
        fid, url, source, org, lang, kind = feed
        status.append((fid, "news.google" in url, len(rows or []), err))
        for title, link, date_s, desc in rows or []:
            title = SUFFIX.sub("", title).strip()
            pub = A.parse_date(date_s)
            if not pub or pub < now - timedelta(hours=hours) or pub > now + timedelta(hours=3):
                continue
            u = A.clean_url(link)
            key = re.sub(r"\W+", "", A.fold(title.lower()))[:80]
            if key in seen or len(title) < 20:
                continue
            seen.add(key)
            path = urlparse(u).path.lower()
            summary = "" if "news.google" in url else A.trim(desc)
            items.append({"title": title, "url": u, "path": path, "source": source, "org": org, "lang": lang,
                          "kind": kind, "summary": summary, "_ts": pub.timestamp(), "feed": fid,
                          "publishedAt": pub.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return items, status


# ---- búsquedas de Google Noticias con palabras positivas, limitadas a cada medio tico
import urllib.parse as _up
KW_Q = ('premio OR "primer lugar" OR rescatan OR donan OR voluntarios OR tortugas OR reforestación OR beca OR '
        'descubren OR inauguran OR récord OR "nueva especie" OR medalla OR ganan OR reconocimiento')
for _s, _src, _org in [("crhoy.com", "CRHoy", "crhoy"), ("teletica.com", "Teletica", "teletica"),
                       ("repretel.com", "Repretel", "repretel"), ("nacion.com", "La Nación (Costa Rica)", "grupo-nacion"),
                       ("diarioextra.com", "Diario Extra", "diarioextra"), ("elmundo.cr", "El Mundo CR", "elmundo-cr"),
                       ("delfino.cr", "Delfino", "delfino"), ("ameliarueda.com", "AmeliaRueda.com", "ameliarueda"),
                       ("amprensa.com", "AM Prensa", "amprensa"), ("trivisioncr.com", "Trivisión", "trivision"),
                       ("observador.cr", "El Observador", "observador"), ("semanariouniversidad.com", "Semanario Universidad", "semanario"),
                       ("monumental.co.cr", "Monumental", "monumental")]:
    CR_GOOD_FEEDS.append(("crq-" + _org + "-" + _s.split(".")[0], "https://news.google.com/rss/search?" + _up.urlencode(
        {"q": f"when:3d site:{_s} ({KW_Q})", "hl": "es-419", "gl": "CR", "ceid": "CR:es-419"}), _src, _org, "es", "medio"))


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    items, status = gather(now)
    for s in status:
        print(*s)
    json.dump(items, open("/tmp/cr_items.json", "w"), ensure_ascii=False)
    print(len(items), "items")

