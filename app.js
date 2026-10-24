const TZ = "America/Costa_Rica";
const when = new Intl.DateTimeFormat("es-CR", {
  timeZone: TZ, weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
});
const state = { data: null, cat: "buenas", lang: "all", buenasFilter: "todas", mundoFilter: "todas", mundoInfo: false, olderOpen: {}, cryptoSel: null, sportSel: null };

function fmt(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : when.format(d) + " (hora CR)";
}

function rel(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (Number.isNaN(mins)) return "";
  if (mins < 1) return "ahora";
  if (mins < 60) return "hace " + mins + " min";
  const h = Math.round(mins / 60);
  if (h < 36) return "hace " + h + " h";
  return "hace " + Math.round(h / 24) + " d";
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function renderSchedule(data) {
  const box = document.getElementById("schedule");
  box.innerHTML = "";
  const late = Date.now() > new Date(data.nextRefreshAt).getTime() + 90 * 60000;
  const l1 = el("span");
  l1.append(el("strong", null, "Última actualización: "), fmt(data.updatedAt));
  const l2 = el("span");
  l2.append(el("strong", null, "Próxima: "), "aprox. " + fmt(data.nextRefreshAt));
  box.append(l1, el("br"), l2);
  if (late) {
    box.append(el("br"), el("span", "due", "La actualización automática va atrasada. Estos son los últimos datos guardados."));
  }
}

const crc = (v) => "₡" + Number(v).toLocaleString("es-CR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const day = new Intl.DateTimeFormat("es-CR", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short" });
const fday = (d) => day.format(new Date(d + "T12:00:00Z"));

function renderFx(data) {
  const fx = data.exchange;
  const box = document.getElementById("fx");
  if (!fx || !fx.dolar) return;
  box.hidden = false;
  box.innerHTML = "";
  const d = fx.dolar;
  const grid = el("div", "fx-grid");
  function cell(label, value, delta, note) {
    const c = el("div", "fx-cell");
    c.append(el("span", "fx-label", label), el("span", "fx-val", value));
    if (delta != null && delta !== 0) {
      c.append(el("span", "fx-delta " + (delta > 0 ? "up" : "down"), (delta > 0 ? "▲ " : "▼ ") + crc(Math.abs(delta)).replace("₡", "₡")));
    } else if (delta === 0) {
      c.append(el("span", "fx-delta", "= sin cambio"));
    }
    if (note) c.append(el("span", "fx-note", note));
    return c;
  }
  grid.append(cell("Dólar compra", crc(d.compra), d.cambioCompra),
              cell("Dólar venta", crc(d.venta), d.cambioVenta));
  if (fx.euro) grid.append(cell("Euro", crc(fx.euro.colones), null,
    "US$" + fx.euro.dolares.toFixed(4) + (fx.euro.fecha !== d.fecha ? " · " + fday(fx.euro.fecha) : "")));
  box.append(el("p", "fx-title", "Tipo de cambio de referencia BCCR · " + fday(d.fecha)), grid);
  const link = (text, href, cls) => {
    const a = el("a", cls || null, text);
    a.href = href; a.target = "_blank"; a.rel = "noopener";
    return a;
  };
  const credit = el("p", "fx-credit");
  credit.append("Datos: ", link("TipoCambioCR", "https://www.tipocambiocr.net/"));
  if (fx.euro) credit.append(" · Euro: Hacienda");
  box.append(credit);
  if (fx.manana && fx.manana.venta) {
    const m = el("p", "fx-tomorrow");
    m.append(el("strong", null, "Mañana (" + fday(fx.manana.fecha) + "): "),
      (fx.manana.compra ? "compra " + crc(fx.manana.compra) + " · " : "") + "venta " + crc(fx.manana.venta));
    box.append(m);
  }
  const meta = el("p", "fx-meta");
  let txt = d.anterior ? "Cambio vs " + fday(d.anterior.fecha) + ". " : "";
  if (fx.mejorVenta) txt += "Mejor venta en ventanilla: " + fx.mejorVenta.entidad + " " + crc(fx.mejorVenta.venta) + ". ";
  if (fx.mejorCompra) txt += "Mejor compra: " + fx.mejorCompra.entidad + " " + crc(fx.mejorCompra.compra) + ".";
  meta.textContent = txt;
  box.append(meta);
  if (fx.ventanilla && fx.ventanilla.length) {
    const det = el("details", "fx-banks");
    const n = fx.ventanilla.reduce((a, g) => a + g.rows.length, 0);
    det.append(el("summary", null, "Ver bancos y casas de cambio (" + n + ")"));
    fx.ventanilla.forEach((g) => {
      det.append(el("p", "fx-group", g.label));
      const t = el("table", "fx-table");
      const hr = el("tr");
      ["Entidad", "Compra", "Venta"].forEach((h) => hr.append(el("th", null, h)));
      t.append(hr);
      g.rows.forEach((r) => {
        const tr = el("tr");
        tr.append(el("td", null, r.entidad), el("td", null, crc(r.compra)), el("td", null, crc(r.venta)));
        t.append(tr);
      });
      det.append(t);
    });
    box.append(det);
  }
  box.append(link("Ver más en TipoCambioCR ↗", "https://www.tipocambiocr.net/", "fx-more"));
  const src = el("p", "fx-src");
  src.append("Referencia oficial del Banco Central de Costa Rica. Consultado " + fmt(fx.consultado) + ".");
  box.append(src);
}

// Precios de cripto (CoinGecko, cada ~3 h): primera sección de la pestaña Criptomonedas.
const usdFmt = (v) => {
  const a = Math.abs(v);
  const d = a >= 1000 ? 0 : a >= 1 ? 2 : 4;
  return "US$" + Number(v).toLocaleString("es-CR", { minimumFractionDigits: d, maximumFractionDigits: d });
};
const pctFmt = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toLocaleString("es-CR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " %";
const bigUsd = (v) => v >= 1e12 ? "US$" + (v / 1e12).toLocaleString("es-CR", { maximumFractionDigits: 2 }) + " billones"
  : "US$" + (v / 1e9).toLocaleString("es-CR", { maximumFractionDigits: 1 }) + " mil millones";
const SVGNS = "http://www.w3.org/2000/svg";

function sparkSvg(vals, w, h, cls, area) {
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", "0 0 " + w + " " + h);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", cls);
  svg.setAttribute("aria-hidden", "true");
  if (!vals || vals.length < 2) return svg;
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1, pad = 2;
  const pts = vals.map((v, i) => [(i / (vals.length - 1)) * w, pad + (1 - (v - min) / span) * (h - pad * 2)]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  if (area) {
    const a = document.createElementNS(SVGNS, "path");
    a.setAttribute("d", d + " L" + w + " " + h + " L0 " + h + " Z");
    a.setAttribute("class", "cx-area");
    svg.append(a);
  }
  const line = document.createElementNS(SVGNS, "path");
  line.setAttribute("d", d);
  line.setAttribute("class", "cx-line");
  line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(line);
  return svg;
}

function trend(v) { return v > 0 ? " up" : v < 0 ? " down" : ""; }

function renderCrypto(list) {
  const cp = state.data.cryptoPrices;
  if (!cp || !cp.coins || !cp.coins.length) return;
  const sec = el("section", "cx");
  sec.setAttribute("aria-label", "Precios de criptomonedas");
  const head = el("div", "cx-head");
  head.append(el("h2", "cx-title", "Precios"), el("span", "cx-sub", "US$ · gráfica de 7 días"));
  sec.append(head);

  if (!cp.coins.some((c) => c.id === state.cryptoSel)) state.cryptoSel = cp.coins[0].id;
  const c = cp.coins.find((x) => x.id === state.cryptoSel);
  const wk = c.spark7d && c.spark7d.length > 1 ? c.spark7d : null;
  const ch7 = c.change7d != null ? c.change7d : wk ? (wk[wk.length - 1] / wk[0] - 1) * 100 : null;
  const feat = el("div", "cx-feat" + trend(ch7));
  const ft = el("div", "cx-ftop");
  const nm = el("p", "cx-fname");
  nm.append(el("strong", null, c.name), " ", el("span", null, c.symbol));
  const pr = el("p", "cx-fprice", usdFmt(c.price));
  const fx = state.data.exchange && state.data.exchange.dolar;
  ft.append(nm, pr);
  if (fx && fx.venta) ft.append(el("p", "cx-fcrc", "≈ " + crc(c.price * fx.venta).replace(/,\d\d$/, "") + " (venta BCCR)"));
  const chips = el("p", "cx-fchips");
  chips.append(el("span", "cx-chg" + trend(c.change24h), pctFmt(c.change24h) + " 24 h"));
  if (ch7 != null) chips.append(el("span", "cx-chg" + trend(ch7), pctFmt(ch7) + " 7 d"));
  ft.append(chips);
  feat.append(ft);
  if (wk) {
    const chart = el("div", "cx-chart");
    chart.append(sparkSvg(wk, 320, 110, "cx-big", true),
      el("span", "cx-max", "máx. " + usdFmt(Math.max(...wk))),
      el("span", "cx-min", "mín. " + usdFmt(Math.min(...wk))));
    feat.append(chart);
    const ax = el("div", "cx-axis");
    ax.append(el("span", null, "hace 7 d"), el("span", null, "ahora"));
    feat.append(ax);
  }
  const st = el("p", "cx-stats");
  const bits = [];
  if (c.low24h != null && c.high24h != null) bits.push("24 h: " + usdFmt(c.low24h) + " – " + usdFmt(c.high24h));
  if (c.marketCap) bits.push("Cap. de mercado " + bigUsd(c.marketCap));
  st.textContent = bits.join(" · ");
  feat.append(st);
  sec.append(feat);

  const rows = el("ul", "cx-list");
  cp.coins.forEach((x) => {
    const li = el("li");
    const b = el("button", "cx-row" + (x.id === c.id ? " on" : "") + trend(x.change24h));
    b.type = "button";
    b.setAttribute("aria-pressed", String(x.id === c.id));
    b.setAttribute("aria-label", x.name + ", " + usdFmt(x.price) + ", " + pctFmt(x.change24h) + " en 24 horas. Ver gráfica");
    const id = el("span", "cx-id");
    id.append(el("span", "cx-sym", x.symbol), el("span", "cx-name", x.name));
    const right = el("span", "cx-right");
    right.append(el("span", "cx-price", usdFmt(x.price)), el("span", "cx-chg" + trend(x.change24h), pctFmt(x.change24h)));
    b.append(id, sparkSvg(x.spark7d, 72, 26, "cx-spark", false), right);
    b.addEventListener("click", () => {
      state.cryptoSel = x.id;
      const old = list.querySelector(".cx");
      const y = window.scrollY;
      const tmp = el("div");
      renderCrypto(tmp);
      if (old && tmp.firstChild) old.replaceWith(tmp.firstChild);
      window.scrollTo({ top: y });
      // Si la gráfica quedó fuera de la vista (bajo las pestañas fijas), se sube hasta ella.
      const feat = list.querySelector(".cx-feat");
      const tabs = document.getElementById("tabs").getBoundingClientRect().bottom;
      if (feat && feat.getBoundingClientRect().top < tabs) {
        window.scrollTo({ top: window.scrollY + list.querySelector(".cx").getBoundingClientRect().top - tabs - 8, behavior: "smooth" });
      }
    });
    li.append(b);
    rows.append(li);
  });
  sec.append(rows);

  const foot = el("p", "cx-foot");
  const a = el("a", null, cp.source);
  a.href = cp.sourceUrl; a.target = "_blank"; a.rel = "noopener";
  foot.append("Datos: ", a, " · actualizado " + rel(cp.fetchedAt || cp.updatedAt) +
    ". Se renuevan con cada actualización (cada ~3 h); no son en tiempo real. Toca una moneda para ver su gráfica.");
  sec.append(foot);
  list.append(sec);
}

// Resultados deportivos (ESPN, cada ~3 h): pestaña Deportes. Foto de cada actualización, no en vivo.
const hourOnly = new Intl.DateTimeFormat("es-CR", { timeZone: TZ, hour: "numeric", minute: "2-digit" });
const dayOnly = new Intl.DateTimeFormat("es-CR", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" });
const crDay = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d);
function gameWhen(g) {
  const d = new Date(g.start);
  if (Number.isNaN(d.getTime())) return "";
  const today = crDay(new Date()), dd = crDay(d);
  const tmw = crDay(new Date(Date.now() + 864e5)), yst = crDay(new Date(Date.now() - 864e5));
  const dayTxt = dd === today ? "Hoy" : dd === tmw ? "Mañana" : dd === yst ? "Ayer" : dayOnly.format(d);
  if (g.state !== "pre") return dayTxt;
  return dayTxt + (g.timeTbd ? " · hora por definir" : " · " + hourOnly.format(d));
}

function sideRow(g, sd, tennis) {
  const lost = g.state === "post" && sd.winner === false;
  const row = el("div", "gm-side" + (sd.winner ? " win" : "") + (lost ? " lose" : ""));
  const who = el("span", "gm-who");
  if (sd.logo || sd.flag) {
    const img = el("img", sd.logo ? "gm-logo" : "gm-flag");
    img.src = sd.logo || sd.flag; img.alt = ""; img.loading = "lazy"; img.decoding = "async";
    img.width = 22; img.height = sd.logo ? 22 : 15;
    img.addEventListener("error", () => img.remove());
    who.append(img);
  }
  if (sd.rank) who.append(el("span", "gm-rank", String(sd.rank)));
  if (sd.seed) who.append(el("span", "gm-rank", "(" + sd.seed + ")"));
  const nm = el("span", "gm-name", sd.name);
  if (sd.full && sd.full !== sd.name) nm.title = sd.full;
  who.append(nm);
  if (sd.title) who.append(el("span", "gm-belt", "campeón"));
  if (sd.record) who.append(el("span", "gm-rec", sd.record));
  row.append(who);
  if (tennis) {
    const sets = el("span", "gm-sets");
    (sd.sets || []).forEach((x) => {
      const c = el("span", "gm-set", String(x.v));
      if (x.tb != null) c.append(el("sup", null, String(x.tb)));
      sets.append(c);
    });
    row.append(sets);
  } else if (sd.score != null) {
    row.append(el("span", "gm-score", String(sd.score)));
  } else if (sd.winner) {
    row.append(el("span", "gm-score gm-check", "Ganó"));
  }
  return row;
}

function gameCard(g, lg) {
  const art = el("article", "gm " + g.state);
  const top = el("div", "gm-top");
  const st = el("span", "gm-status");
  if (g.state === "in") st.append(el("span", "gm-live", "En juego"), " " + (g.status || ""));
  else st.append(g.status ? g.status + " · " + gameWhen(g) : gameWhen(g));
  top.append(st);
  if (g.note) top.append(el("span", "gm-note", g.note));
  art.append(top);
  if (g.group) art.append(el("p", "gm-group", g.group));
  const tennis = lg.id === "tenis";
  g.sides.forEach((sd) => art.append(sideRow(g, sd, tennis)));
  const od = oddsBlock(g);
  if (od) art.append(od);
  const meta = [];
  if (g.state === "in" && !spLive.at[lg.id]) meta.push("marcador al actualizar");
  if (g.tv && g.state !== "post") meta.push(g.tv);
  if (meta.length || g.link) {
    const m = el("p", "gm-meta", meta.join(" · "));
    if (g.link) {
      const a = el("a", null, "Ver en ESPN ↗");
      a.href = g.link; a.target = "_blank"; a.rel = "noopener noreferrer";
      if (meta.length) m.append(" · ");
      m.append(a);
    }
    art.append(m);
  }
  return art;
}

// ── Marcadores al momento: al abrir Deportes la app pide la liga elegida directo a ESPN (permite CORS)
// y la vuelve a pedir cada 60 s mientras haya partidos en juego (cada 5 min si no). Si ESPN falla,
// queda la foto de la última actualización (noticias.json → sports). Mismo formato que resultados.py.
const ESPN = "https://site.api.espn.com/apis/site/v2/sports/";
const SP_LEAGUES = {
  nfl: { path: "football/nfl", mode: "week", label: "NFL", name: "NFL", official: "https://www.nfl.com/scores/", officialName: "nfl.com" },
  cfb: { path: "football/college-football", mode: "week", label: "CFB", name: "Fútbol americano universitario (Top 25)", official: "https://www.ncaa.com/scoreboard/football/fbs", officialName: "ncaa.com" },
  nba: { path: "basketball/nba", mode: "days", label: "NBA", name: "NBA", official: "https://www.nba.com/games", officialName: "nba.com" },
  cbb: { path: "basketball/mens-college-basketball", mode: "days", label: "CBB", name: "Baloncesto universitario masculino", official: "https://www.ncaa.com/scoreboard/basketball-men/d1", officialName: "ncaa.com" },
  mlb: { path: "baseball/mlb", mode: "days", label: "MLB", name: "MLB", official: "https://www.mlb.com/scores", officialName: "mlb.com" },
  nhl: { path: "hockey/nhl", mode: "days", label: "NHL", name: "NHL", official: "https://www.nhl.com/scores", officialName: "nhl.com" },
  tenis: { path: null, mode: "tennis", label: "Tenis", name: "Tenis (ATP y WTA, individuales)", official: "https://www.flashscore.com/tennis/", officialName: "flashscore.com" },
  mma: { path: "mma/ufc", mode: "mma", label: "MMA", name: "MMA (UFC)", official: "https://www.flashscore.com/mma/", officialName: "flashscore.com" },
};
// Si la actualización no trajo marcadores, se arma la pestaña vacía y se llena desde ESPN.
function spEnsure() {
  if (state.data.sports && state.data.sports.leagues && state.data.sports.leagues.length) return state.data.sports;
  state.data.sports = { source: "ESPN", sourceUrl: "https://www.espn.com/", fetchedAt: null, default: "nfl", skeleton: true,
    leagues: Object.entries(SP_LEAGUES).map(([id, c]) => ({ id, label: c.label, name: c.name, official: c.official,
      officialName: c.officialName, games: [], counts: { in: 0, post: 0, pre: 0 } })) };
  return state.data.sports;
}
const spLive = { at: {}, busy: {}, err: {}, timer: null };
const SP_ORD = { 1: "1.º", 2: "2.º", 3: "3.º", 4: "4.º" };
const SP_ROUNDS = { "Round 1": "1.ª ronda", "Round 2": "2.ª ronda", "Round 3": "3.ª ronda", "Round 4": "4.ª ronda",
  "Round of 16": "Octavos", Quarterfinal: "Cuartos de final", Quarterfinals: "Cuartos de final",
  Semifinal: "Semifinal", Semifinals: "Semifinal", Final: "Final" };
const SP_WEIGHTS = { Heavyweight: "Peso pesado", "Light Heavyweight": "Peso semipesado", Middleweight: "Peso mediano",
  Welterweight: "Peso wélter", Lightweight: "Peso ligero", Featherweight: "Peso pluma", Bantamweight: "Peso gallo",
  Flyweight: "Peso mosca", "W Strawweight": "Peso paja femenino", "W Flyweight": "Peso mosca femenino",
  "W Bantamweight": "Peso gallo femenino", "W Featherweight": "Peso pluma femenino", Catchweight: "Peso pactado" };
const SP_SPECIAL = { STATUS_POSTPONED: "Pospuesto", STATUS_CANCELED: "Cancelado", STATUS_SUSPENDED: "Suspendido",
  STATUS_DELAYED: "Retrasado", STATUS_RAIN_DELAY: "Retrasado por lluvia", STATUS_FORFEIT: "Forfeit",
  STATUS_WALKOVER: "Walkover (W.O.)", STATUS_RETIRED: "Final (retiro)", STATUS_ABANDONED: "Abandonado",
  STATUS_HALFTIME: "Medio tiempo", STATUS_END_PERIOD: "Fin del periodo" };

function spNum(v) { const f = parseFloat(v); return Number.isFinite(f) ? f : null; }

function spStatus(st, sport) {
  const t = st.type || {}, name = t.name || "", stt = t.state || "";
  const short = t.shortDetail || t.detail || "", period = st.period || 0, clock = st.displayClock || "";
  if (SP_SPECIAL[name]) {
    if (name === "STATUS_END_PERIOD" && sport === "football") return "Fin del " + (SP_ORD[period] || period + ".º") + " cuarto";
    if (name === "STATUS_END_PERIOD" && sport === "hockey") return "Intermedio";
    return SP_SPECIAL[name];
  }
  if (stt === "post") {
    let extra = "";
    const inn = short.match(/\/(\d+)$/);
    if (inn && sport === "baseball") extra = " (" + inn[1] + " entradas)";
    else if (short.includes("SO")) extra = " (penales)";
    else if (short.includes("OT")) extra = " (tiempo extra)";
    return "Final" + extra;
  }
  if (stt === "in") {
    if (sport === "baseball") {
      const m = short.match(/^(Top|Bot|Bottom|Mid|End)\w*\s+(\d+)/);
      return m ? { Top: "Alta", Bot: "Baja", Bottom: "Baja", Mid: "Mitad", End: "Fin" }[m[1]] + " " + m[2] + ".ª" : "En juego";
    }
    if (sport === "mma") return period ? "En curso · " + period + ".º asalto" : "En curso";
    if (sport === "tennis") return "En juego";
    let unit = { football: "cuarto", basketball: period <= 4 ? "cuarto" : "", hockey: "periodo" }[sport] || "";
    if (sport === "basketball" && short.toLowerCase().includes("college")) unit = "tiempo";
    const ot = (sport === "basketball" && period > 4) || (sport === "football" && period > 4) || (sport === "hockey" && period > 3);
    const p = ot ? "Tiempo extra" : (SP_ORD[period] || period + ".º") + " " + unit;
    return (p + (clock && clock !== "0:00" && clock !== "0.0" ? " · " + clock : "")).trim();
  }
  return "";
}

// Cuotas americanas: «-162» → -162, «+136» → 136, «EVEN» → 100.
function spAmerican(v) {
  if (v == null) return null;
  const t = String(v).trim().toUpperCase();
  if (t === "EVEN" || t === "EV" || t === "PK") return 100;
  const m = t.match(/^([+-]?)(\d{3,5})$/);
  return m ? (m[1] === "-" ? -1 : 1) * parseInt(m[2], 10) : null;
}
const spImplied = (o) => (!o ? null : o > 0 ? 100 / (o + 100) : -o / (-o + 100));
const spClose = (s) => (s && (s.close || s.current || s.open)) || {};
const SP_SPREAD = { baseball: "Run line", hockey: "Puck line" };

function spOdds(comp, sport) {
  const lst = (comp.odds || []).slice().sort((a, b) => ((a.provider || {}).priority ?? 99) - ((b.provider || {}).priority ?? 99));
  if (!lst.length) return null;
  const o = lst[0], ml = o.moneyline || {}, ps = o.pointSpread || {}, tot = o.total || {};
  const mlA = spAmerican(spClose(ml.away).odds), mlH = spAmerican(spClose(ml.home).odds);
  const sa = spClose(ps.away), sh = spClose(ps.home), ov = spClose(tot.over), un = spClose(tot.under);
  let tl = spNum(o.overUnder);
  if (tl == null && ov.line) tl = spNum(String(ov.line).replace(/^[ou]/, ""));
  const out = {
    provider: (o.provider || {}).displayName || (o.provider || {}).name || null,
    details: o.details || null,
    ml: mlA != null || mlH != null ? { away: mlA, home: mlH } : null,
    spread: sa.line || sh.line ? { name: SP_SPREAD[sport] || "Hándicap",
      away: { line: sa.line || null, odds: spAmerican(sa.odds) }, home: { line: sh.line || null, odds: spAmerican(sh.odds) } } : null,
    total: tl != null ? { line: tl, over: spAmerican(ov.odds), under: spAmerican(un.odds) } : null,
    fav: null, favProb: null,
  };
  const pa = spImplied(mlA), ph = spImplied(mlH);
  if (pa && ph) {
    if (Math.abs(pa - ph) < 0.005) out.fav = "even";
    else { out.fav = pa > ph ? "away" : "home"; out.favProb = Math.round((100 * Math.max(pa, ph)) / (pa + ph)); }
  } else {
    const la = spNum(sa.line), lh = spNum(sh.line);
    if (la != null && la < 0) out.fav = "away";
    else if (lh != null && lh < 0) out.fav = "home";
    else if (la === 0 || lh === 0) out.fav = "even";
  }
  return out.ml || out.spread || out.total ? out : null;
}

function spTeamGames(data, sport) {
  const games = [];
  ((data && data.events) || []).forEach((e) => {
    const comp = (e.competitions || [{}])[0];
    const st = comp.status || e.status || {};
    const sides = (comp.competitors || []).map((c) => {
      const t = c.team || {};
      const rec = (c.records || []).find((r) => r.type === "total" || r.name === "overall");
      const rank = (c.curatedRank || {}).current;
      return { name: t.shortDisplayName || t.displayName || t.name || "?", full: t.displayName || null, abbr: t.abbreviation || null,
        logo: t.logo || null, score: c.score === "" || c.score == null ? null : c.score, winner: c.winner,
        record: rec ? rec.summary : null, rank: Number.isInteger(rank) && rank > 0 && rank <= 25 ? rank : null, home: c.homeAway === "home" };
    }).sort((a, b) => a.home - b.home);
    if (sides.length !== 2) return;
    const state = (st.type || {}).state || "pre";
    if (state === "pre") sides.forEach((s) => { s.score = null; });
    const link = (e.links || []).find((l) => (l.rel || []).includes("summary"));
    const note = (comp.notes || []).map((n) => n.headline).filter(Boolean)[0];
    const tv = (comp.broadcasts || []).flatMap((b) => b.names || []).join(", ");
    games.push({ id: e.id, start: e.date, state, status: spStatus(st, sport), timeTbd: comp.timeValid === false,
      note: note || null, venue: (comp.venue || {}).fullName || null, tv: tv || null, link: link ? link.href : null, sides,
      odds: state === "pre" || state === "in" ? spOdds(comp, sport) : null });
  });
  return games;
}

function spTennis(data, tour) {
  const now = Date.now(), win = 30 * 3600e3, out = [];
  ((data && data.events) || []).forEach((e) => (e.groupings || []).forEach((g) => {
    const slug = (g.grouping || {}).slug || "";
    if (slug !== "mens-singles" && slug !== "womens-singles") return;
    (g.competitions || []).forEach((c) => {
      const d = new Date(c.date).getTime();
      if (!(Math.abs(d - now) <= win)) return;
      const comps = c.competitors || [];
      const names = comps.map((x) => (x.athlete || {}).displayName);
      if (comps.length !== 2 || !names.every(Boolean) || names.includes("TBD")) return;
      const st = c.status || {}, rnd = (c.round || {}).displayName || "", qual = rnd.includes("Qualif");
      const sides = comps.slice().sort((a, b) => (a.order || 0) - (b.order || 0)).map((x) => {
        const a = x.athlete || {};
        return { name: a.displayName, short: a.shortName, country: (a.flag || {}).alt, flag: (a.flag || {}).href,
          seed: x.seed || null, winner: x.winner,
          sets: (x.linescores || []).filter((l) => spNum(l.value) != null).map((l) => ({ v: spNum(l.value), tb: l.tiebreak })) };
      });
      out.push({ id: c.id, start: c.date, state: (st.type || {}).state || "pre", status: spStatus(st, "tennis"),
        timeTbd: c.timeValid === false, group: e.name + " · " + tour,
        note: (qual ? "Clasificación" : SP_ROUNDS[rnd] || rnd) + " · " + (slug.startsWith("mens") ? "Masculino" : "Femenino"),
        qualifying: qual, link: null, sides });
    });
  }));
  const o = { in: 0, post: 1, pre: 2 };
  out.sort((a, b) => a.qualifying - b.qualifying || (o[a.state] ?? 3) - (o[b.state] ?? 3));
  const main = out.filter((g) => !g.qualifying);
  return (main.length >= 6 ? main : out).slice(0, 24);
}

function spMma(data) {
  const out = [];
  ((data && data.events) || []).forEach((e) => {
    const link = (e.links || []).find((l) => (l.rel || []).includes("summary"));
    (e.competitions || []).slice().reverse().forEach((c, i) => {
      const st = c.status || {};
      const sides = (c.competitors || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0)).map((x) => {
        const a = x.athlete || {};
        const rec = (x.records || []).find((r) => r.name === "overall");
        return { name: a.displayName || "?", short: a.shortName, country: (a.flag || {}).alt, flag: (a.flag || {}).href,
          record: rec ? rec.summary : null, winner: x.winner, title: (a.accolades || []).some((ac) => ac.type === "Belt") };
      });
      if (sides.length !== 2) return;
      const wc = (c.type || {}).abbreviation || "";
      const state = (st.type || {}).state || "pre";
      out.push({ id: c.id, start: c.date || e.date, state, status: spStatus(st, "mma"), group: e.name,
        note: (i === 0 ? "Pelea estelar · " : "") + (SP_WEIGHTS[wc] || wc), link: link ? link.href : null, sides,
        odds: state === "pre" ? spOdds(c, "mma") : null });
    });
  });
  return out;
}

async function spGet(url) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ctl.signal });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  } finally { clearTimeout(t); }
}

const spTs = (iso) => { const t = new Date(iso).getTime(); return Number.isNaN(t) ? 0 : t; };

async function spFetchLeague(id) {
  const cfg = SP_LEAGUES[id];
  const sport = (cfg.path || "tennis/").split("/")[0];
  let games = [];
  if (cfg.mode === "tennis") {
    const rs = await Promise.allSettled([["atp", "ATP"], ["wta", "WTA"]].map(([t, l]) => spGet(ESPN + "tennis/" + t + "/scoreboard").then((d) => spTennis(d, l))));
    if (rs.every((r) => r.status === "rejected")) throw rs[0].reason;
    rs.forEach((r) => { if (r.status === "fulfilled") games = games.concat(r.value); });
  } else if (cfg.mode === "mma") {
    games = spMma(await spGet(ESPN + cfg.path + "/scoreboard"));
  } else if (cfg.mode === "week") {
    games = spTeamGames(await spGet(ESPN + cfg.path + "/scoreboard"), sport);
  } else {
    const days = [-1, 0, 1].map((d) => crDay(new Date(Date.now() + d * 864e5)).replace(/-/g, ""));
    const all = await Promise.all(days.map((d) => spGet(ESPN + cfg.path + "/scoreboard?dates=" + d)));
    const seen = new Set();
    all.forEach((d) => spTeamGames(d, sport).forEach((g) => { if (!seen.has(g.id)) { seen.add(g.id); games.push(g); } }));
    if (!games.length) games = spTeamGames(await spGet(ESPN + cfg.path + "/scoreboard"), sport).filter((g) => g.state === "pre");
  }
  const o = { in: 0, post: 1, pre: 2 };
  games.sort((a, b) => (o[a.state] ?? 3) - (o[b.state] ?? 3) ||
    (a.state === "post" ? spTs(b.start) - spTs(a.start) : spTs(a.start) - spTs(b.start)));
  return games;
}

// Pide la liga a ESPN si la copia tiene más de 45 s (o si force). Repinta solo si sigues en Deportes.
async function spRefresh(id, force) {
  if (!state.data) return;
  const sp = spEnsure();
  if (!SP_LEAGUES[id] || spLive.busy[id]) return;
  if (!force && spLive.at[id] && Date.now() - spLive.at[id] < 45000) return;
  spLive.busy[id] = true;
  if (state.cat === "deportes") spPaintStatus();
  try {
    const games = await spFetchLeague(id);
    const lg = sp.leagues.find((l) => l.id === id);
    if (lg) {
      lg.games = games;
      lg.counts = { in: 0, post: 0, pre: 0 };
      games.forEach((g) => { if (g.state in lg.counts) lg.counts[g.state] += 1; });
      delete lg.error;
    }
    spLive.at[id] = Date.now();
    delete spLive.err[id];
  } catch (e) {
    spLive.err[id] = Date.now();
  } finally {
    spLive.busy[id] = false;
  }
  if (state.cat === "deportes") { renderTabs(); renderList(); }
  spSchedule();
}

// Siguiente vuelta: 60 s si la liga elegida tiene partidos en juego (o uno empieza en < 20 min); si no, 5 min.
function spSchedule() {
  clearTimeout(spLive.timer);
  if (state.cat !== "deportes" || document.hidden) return;
  const sp = state.data.sports, lg = sp && sp.leagues.find((l) => l.id === state.sportSel);
  if (!lg) return;
  const soon = lg.games.some((g) => g.state === "in" || (g.state === "pre" && spTs(g.start) - Date.now() < 20 * 60000));
  spLive.timer = setTimeout(() => spRefresh(state.sportSel, true), soon ? 60000 : 300000);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.data && state.cat === "deportes") spRefresh(state.sportSel, false);
  else clearTimeout(spLive.timer);
});

// Línea de estado bajo el título: en vivo desde ESPN, cargando, o foto de la última actualización.
function spStatusText(lg) {
  const id = lg.id;
  if (spLive.busy[id] && !spLive.at[id]) return { cls: "load", txt: "Buscando marcadores al momento…" };
  if (spLive.at[id]) {
    const s = Math.round((Date.now() - spLive.at[id]) / 1000);
    return { cls: "ok", txt: "Al momento · ESPN " + (s < 60 ? "hace " + s + " s" : rel(new Date(spLive.at[id]).toISOString())) +
      (spLive.err[id] ? " (el último intento falló)" : "") };
  }
  const fa = state.data.sports.fetchedAt;
  if (spLive.err[id]) return { cls: "old", txt: fa ? "Sin conexión con ESPN: datos de la actualización de " + rel(fa) : "Sin conexión con ESPN" };
  return { cls: "old", txt: fa ? "Datos de la actualización de " + rel(fa) : "Sin datos guardados" };
}
function spPaintStatus() {
  const box = document.querySelector(".sp-live");
  const sp = state.data.sports, lg = sp && sp.leagues.find((l) => l.id === state.sportSel);
  if (!box || !lg) return;
  const s = spStatusText(lg);
  box.className = "sp-live " + s.cls;
  box.querySelector(".sp-live-txt").textContent = s.txt;
}

// ── Líneas del mercado bajo cada partido. Cuotas americanas: −162 = apostar 162 para ganar 100;
// +136 = apostar 100 para ganar 136.
const spFmt = (o) => (o == null ? "—" : o > 0 ? "+" + o : "−" + Math.abs(o));
const spLine = (l) => (l == null ? "" : String(l).replace(/^-/, "−"));
function oddsBlock(g) {
  const o = g.odds;
  if (!o) return null;
  const [away, home] = g.sides;
  const nm = (sd) => sd.abbr || sd.short || sd.name;
  const box = el("div", "od");
  const fav = el("p", "od-fav");
  fav.append(el("span", "od-tag", "Favorito del mercado"));
  if (o.fav === "even") fav.append(" Parejo (sin favorito claro)");
  else if (o.fav) {
    const sd = o.fav === "away" ? away : home;
    fav.append(" ", el("strong", null, sd.name));
    if (o.favProb) fav.append(el("span", "od-prob", " · " + o.favProb + " % implícito"));
  } else fav.append(" —");
  box.append(fav);
  if (o.favProb) {
    const bar = el("div", "od-bar");
    bar.setAttribute("aria-hidden", "true");
    const left = o.fav === "away" ? o.favProb : 100 - o.favProb;
    const a = el("span", "od-bar-a" + (o.fav === "away" ? " fav" : "")); a.style.inlineSize = left + "%";
    const h = el("span", "od-bar-h" + (o.fav === "home" ? " fav" : "")); h.style.inlineSize = (100 - left) + "%";
    bar.append(a, h);
    box.append(bar);
  }
  const t = el("div", "od-grid");
  t.setAttribute("role", "table");
  t.setAttribute("aria-label", "Líneas del mercado");
  const cell = (txt, cls) => { const c = el("span", cls || "od-c", txt); c.setAttribute("role", "cell"); return c; };
  const hdr = el("div", "od-row od-h"); hdr.setAttribute("role", "row");
  hdr.append(cell(""), cell("Ganador (ML)"), cell(o.spread ? o.spread.name : "Hándicap"));
  t.append(hdr);
  [["away", away], ["home", home]].forEach(([k, sd]) => {
    const r = el("div", "od-row" + (o.fav === k ? " fav" : "")); r.setAttribute("role", "row");
    const s = o.spread && o.spread[k];
    r.append(cell(nm(sd), "od-c od-team"), cell(o.ml ? spFmt(o.ml[k]) : "—"),
      cell(s && s.line ? spLine(s.line) + (s.odds != null ? " (" + spFmt(s.odds) + ")" : "") : "—"));
    t.append(r);
  });
  box.append(t);
  if (o.total) {
    box.append(el("p", "od-total", "Total " + o.total.line + " · Más " + spFmt(o.total.over) + " / Menos " + spFmt(o.total.under)));
  }
  return box;
}

const SP_UPCOMING_MAX = 10;
function renderSports(list) {
  const sp = spEnsure();
  const sec = el("section", "sp");
  sec.setAttribute("aria-label", "Resultados deportivos");
  const head = el("div", "cx-head");
  head.append(el("h2", "cx-title", "Resultados"), el("span", "cx-sub", "hora CR"));
  sec.append(head);
  if (!sp || !sp.leagues || !sp.leagues.length) {
    sec.append(el("p", "empty", "No se pudieron leer los resultados en esta actualización. Vuelve a revisar en la próxima."));
    list.append(sec);
    return;
  }
  if (!sp.leagues.some((l) => l.id === state.sportSel)) state.sportSel = sp.default || sp.leagues[0].id;
  const bar = el("div", "bfilter mfilter spfilter");
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Elegir liga");
  sp.leagues.forEach((l) => {
    const b = el("button", "bf" + (l.id === state.sportSel ? " on" : "") + (l.games.length ? "" : " zero"));
    b.type = "button";
    b.setAttribute("aria-pressed", String(l.id === state.sportSel));
    if (l.counts && l.counts.in) b.append(el("span", "sp-dot", ""));
    b.append(l.label, el("span", "count", String(l.games.length)));
    b.addEventListener("click", () => { state.sportSel = l.id; renderList(); spRefresh(l.id, false); });
    bar.append(b);
  });
  sec.append(bar);
  // Fila deslizable: deja visible la liga elegida (sin mover la página).
  requestAnimationFrame(() => {
    const on = bar.querySelector(".bf.on");
    if (on && bar.scrollWidth > bar.clientWidth) bar.scrollLeft = on.offsetLeft - (bar.clientWidth - on.offsetWidth) / 2;
  });
  const lg = sp.leagues.find((l) => l.id === state.sportSel);
  const lh = el("div", "sp-lhead");
  lh.append(el("h3", "sp-lname", lg.name));
  const off = el("a", "sp-off", lg.officialName + " ↗");
  off.href = lg.official; off.target = "_blank"; off.rel = "noopener noreferrer";
  lh.append(off);
  sec.append(lh);
  const ls = spStatusText(lg);
  const lv = el("div", "sp-live " + ls.cls);
  lv.setAttribute("role", "status");
  lv.append(el("span", "sp-live-dot"), el("span", "sp-live-txt", ls.txt));
  const rb = el("button", "sp-reload", "Actualizar");
  rb.type = "button";
  rb.addEventListener("click", () => spRefresh(lg.id, true));
  lv.append(rb);
  sec.append(lv);
  const nOdds = lg.games.filter((g) => g.odds).length;
  if (nOdds) sec.append(el("p", "sp-oddsnote", nOdds + (nOdds === 1 ? " partido con líneas" : " partidos con líneas") + " del mercado (" +
    (lg.games.find((g) => g.odds).odds.provider || "casas") + " vía ESPN), bajo cada partido."));
  if (!lg.games.length) {
    sec.append(el("p", "empty sp-empty", spLive.busy[lg.id] ? "Cargando marcadores…" : lg.error || ("Sin partidos de " + lg.label + " en esta actualización (fuera de temporada o días sin juegos).")));
  }
  const groups = [["in", spLive.at[lg.id] ? "En juego" : "En juego al actualizar"], ["post", "Finalizados"], ["pre", "Próximos"]];
  groups.forEach(([stt, title]) => {
    const gs = lg.games.filter((g) => g.state === stt);
    if (!gs.length) return;
    sec.append(el("h4", "sp-gtitle", title + " (" + gs.length + ")"));
    const shown = stt === "pre" ? gs.slice(0, SP_UPCOMING_MAX) : gs;
    shown.forEach((g) => sec.append(gameCard(g, lg)));
    if (gs.length > shown.length) {
      const det = el("details", "sp-more");
      det.append(el("summary", null, "Ver " + (gs.length - shown.length) + " más"));
      gs.slice(SP_UPCOMING_MAX).forEach((g) => det.append(gameCard(g, lg)));
      sec.append(det);
    }
  });
  if (lg.games.some((g) => g.odds)) {
    sec.append(el("p", "od-foot", "Líneas: cuotas americanas de la casa que publica ESPN (" + ((lg.games.find((g) => g.odds).odds.provider) || "DraftKings") +
      "). −150 = apostar 150 para ganar 100; +130 = apostar 100 para ganar 130. «Favorito del mercado» es el lado que la casa paga menos; el % es la probabilidad implícita de esas cuotas sin el margen de la casa. Es lo que dice el mercado, no una predicción nuestra. No es consejo de apuesta ni financiero; las líneas cambian y apostar implica riesgo de perder dinero."));
  }
  const foot = el("p", "cx-foot");
  const a = el("a", null, "ESPN");
  a.href = sp.sourceUrl; a.target = "_blank"; a.rel = "noopener";
  foot.append("Datos vía ", a, " (NFL, CFB, NBA, CBB, MLB, NHL, ATP/WTA y UFC). Al abrir esta pestaña se piden los marcadores al momento y se renuevan cada minuto mientras hay partidos en juego; si ESPN no responde, se muestra la última actualización (cada ~3 h). Toca el sitio oficial de cada liga para el detalle jugada a jugada.");
  sec.append(foot);
  list.append(sec);
}

function renderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  state.data.categories.forEach((c) => {
    const b = el("button", "tab" + (c.id === state.cat ? " on" : ""));
    b.type = "button";
    b.dataset.cat = c.id;
    if (c.kind === "scores") {
      const sp = state.data.sports;
      const live = sp ? sp.leagues.reduce((n, l) => n + ((l.counts && l.counts.in) || 0), 0) : 0;
      b.append(c.label);
      if (live) b.append(el("span", "count live", live + " en juego"));
    } else b.append(c.label, el("span", "count", String(c.stories.length)));
    b.addEventListener("click", () => {
      state.cat = c.id;
      renderTabs();
      renderList();
      window.scrollTo({ top: 0 });
      if (c.kind === "scores") spRefresh(state.sportSel, false);
      else clearTimeout(spLive.timer);
    });
    nav.appendChild(b);
  });
}

// Relato de la historia: lo escribe una IA con todas las fuentes, o es un extracto de frases de varios medios.
function narrLabel(kind, n, lang) {
  if (lang === "en") return kind === "ia" ? "AI-generated summary from " + n + (n === 1 ? " outlet" : " outlets")
    : "Excerpts from " + n + " outlets, no AI";
  return kind === "ia" ? "Resumen generado con IA a partir de " + n + (n === 1 ? " medio" : " medios")
    : "Extracto de " + n + " medios, sin IA";
}

let clampId = 0;
function textBlock(lang, headline, d, primary) {
  const wrap = el("div", "txt " + (primary ? "primary" : "secondary"));
  if (headline) {
    const h = el(primary ? "h2" : "h3");
    if (!primary || state.lang === "all") h.append(el("span", "badge " + lang, lang.toUpperCase()), " ");
    h.append(headline);
    wrap.append(h);
  }
  if (d && d.narr) {
    const box = el("div", "narr " + d.kind);
    const lab = el("p", "narr-label");
    lab.append(el("span", "narr-mark", d.kind === "ia" ? "✦" : "❝"), " ", narrLabel(d.kind, d.n, d.lang));
    const p = el("p", "summary clamp", d.narr);
    p.lang = d.lang;
    p.id = "narr-" + (++clampId);
    const more = el("button", "more-btn", d.lang === "en" ? "Read more" : "Leer más");
    more.type = "button";
    more.hidden = true; // fitClamps lo muestra si el texto no cabe
    more.setAttribute("aria-controls", p.id);
    more.setAttribute("aria-expanded", "false");
    more.addEventListener("click", () => {
      const open = p.classList.toggle("open");
      more.setAttribute("aria-expanded", String(open));
      more.textContent = d.lang === "en" ? (open ? "Show less" : "Read more") : (open ? "Leer menos" : "Leer más");
    });
    box.append(lab, p, more);
    wrap.append(box);
  } else if (d && d.s) {
    const p = el("p", "summary", d.s);
    if (d.src) p.append(el("span", "via", " — " + d.src));
    wrap.append(p);
  }
  return wrap;
}

// «Leer más» solo si el relato no cabe en sus líneas (se mide ya pintado; lo plegado se mide al abrirlo).
function fitClamps(root) {
  root.querySelectorAll(".clamp:not(.open)").forEach((p) => {
    if (!p.clientHeight) return;
    p.nextElementSibling.hidden = p.scrollHeight <= p.clientHeight + 2;
  });
}
let fitTimer;
window.addEventListener("resize", () => {
  clearTimeout(fitTimer);
  fitTimer = setTimeout(() => fitClamps(document.getElementById("list")), 150);
});

function card(s) {
  const art = el("article", "card");
  const top = el("div", "cardtop");
  if (s.subtopicLabel) top.append(el("span", "subtopic st-" + s.subtopic, s.subtopicLabel));
  if (s.cr) top.append(el("span", "chip cr", "Costa Rica"));
  (s.chips || []).forEach((c) => top.append(el("span", "chip", c.label)));
  if (!s.subtopic || s.outlets > 1) {
    top.append(el("span", "outlets" + (s.outlets >= 5 ? " hot" : "") + (state.cat === "posibles" ? " maybe" : ""), s.outlets + " medios"));
  } else {
    top.append(el("span", "outlets one", s.outletNames[0]));
  }
  if (s.fresh) {
    const en = state.lang === "en";
    const label = s.fresh === "nuevo" ? (en ? "New" : "Nuevo") : (en ? "Ongoing" : "Sigue");
    const b = el("span", "fresh " + s.fresh, label);
    if (s.fresh === "sigue" && s.firstShown) b.title = (en ? "Shown since " : "En la app desde ") + fmt(s.firstShown);
    top.append(b);
  }
  top.append(el("span", "time", rel(s.lastArticle || s.lastSeen)));
  art.append(top);

  // Descripción: relato (IA o extracto) en el idioma pedido si existe; si no, el resumen de un medio.
  const kind = s.narrKind;
  const nar = {
    es: s.narrEs ? { narr: s.narrEs, kind, lang: "es", n: s.narrNEs || s.narrN || s.outlets } : null,
    en: s.narrEn ? { narr: s.narrEn, kind, lang: "en", n: s.narrNEn || s.narrN || s.outlets } : null,
  };
  const plain = { es: { s: s.summaryEs, src: s.summaryEsSource }, en: { s: s.summaryEn, src: s.summaryEnSource } };
  const heads = { es: s.headlineEs, en: s.headlineEn };
  let order;
  if (state.lang === "all") order = ["es", "en"].filter((l) => heads[l]).map((l) => [l, nar[l] || plain[l]]);
  else {
    const want = state.lang;
    const hl = heads[want] ? want : (want === "es" ? "en" : "es");
    // Sin titular en el idioma pedido: titular del otro idioma y, si hay, el relato de la IA en el pedido.
    order = [[hl, (kind === "ia" && nar[want]) || nar[hl] || plain[hl]]];
  }
  order.forEach(([lang, d], i) => art.append(textBlock(lang, heads[lang], d, i === 0)));
  const shownNarr = order.some(([, d]) => d && d.narr);

  const det = el("details", "sources");
  const sum = el("summary", null, s.outlets > 1
    ? "Ver fuentes (" + s.sources.length + " notas en " + s.outlets + " medios" +
      (s.extraOutlets ? " + " + s.extraOutlets + (s.extraOutlets === 1 ? " fuente extra que no cuenta" : " fuentes extra que no cuentan") : "") + ")"
    : "Ver fuente" + (s.sources.length > 1 ? "s (" + s.sources.length + " notas)" : ""));
  det.append(sum);
  if (shownNarr && (s.summaryEs || s.summaryEn)) {
    // Los resúmenes tal como los publicó cada medio, para comparar con el relato.
    const orig = el("div", "orig");
    orig.append(el("p", "orig-title", state.lang === "en" ? "Original summaries" : "Resúmenes originales"));
    [["es", s.summaryEs, s.summaryEsSource], ["en", s.summaryEn, s.summaryEnSource]].forEach(([l, t, src]) => {
      if (!t) return;
      const q = el("blockquote");
      q.lang = l;
      q.append(el("p", null, t));
      const c = el("p", "srcmeta");
      c.append(el("strong", null, src || ""), " ", el("span", "badge " + l, l.toUpperCase()));
      q.append(c);
      orig.append(q);
    });
    det.append(orig);
  }
  const ul = el("ul");
  s.sources.forEach((x) => {
    const li = el("li");
    const a = el("a", null, x.title);
    a.href = x.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    const meta = el("div", "srcmeta");
    meta.append(el("strong", null, x.source), " ", el("span", "badge " + x.lang, x.lang.toUpperCase()), " " + fmt(x.publishedAt));
    li.append(meta, a);
    ul.append(li);
  });
  det.append(ul);
  art.append(det);
  if (s.alsoOnReddit && s.alsoOnReddit.length) {
    const r = el("p", "reddit", "También en Reddit: ");
    s.alsoOnReddit.forEach((x, i) => {
      const a = el("a", null, "r/" + x.sub);
      a.href = x.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      if (i) r.append(", ");
      r.append(a);
    });
    art.append(r);
  }
  return art;
}

function renderList() {
  const list = document.getElementById("list");
  list.innerHTML = "";
  const cat = state.data.categories.find((c) => c.id === state.cat);
  if (state.cat === "cripto") renderCrypto(list);
  document.querySelector(".langs").style.display = cat && cat.kind === "scores" ? "none" : "";
  if (cat && cat.kind === "scores") { renderSports(list); return; }
  if (!cat || (!cat.stories.length && cat.id !== "mundo")) {
    let msg = "En esta actualización ninguna historia de esta categoría fue publicada por 3 o más medios distintos. Vuelve a revisar en la próxima actualización.";
    if (state.cat === "buenas") msg = "Ahora mismo no hay buenas noticias confirmadas por un medio confiable.";
    if (cat && cat.group === "region") msg = "En esta actualización ninguna noticia de " + cat.label + " fue publicada por 3 o más medios distintos. Vuelve a revisar en la próxima actualización.";
    if (state.cat === "posibles") msg = "En esta actualización no hay historias publicadas por 2 medios distintos fuera de las ya confirmadas.";
    if (state.cat === "cripto") msg = "En esta actualización ninguna noticia de criptomonedas fue publicada por 3 o más medios distintos, así que no hay nada verificado que mostrar. Vuelve a revisar en la próxima actualización.";
    list.append(el("p", "empty", msg));
    return;
  }
  if (cat.id === "posibles") {
    list.append(el("p", "note warn", "Sin confirmar todavía: estas historias las publican solo 2 medios distintos, no los 3 o más que exigen las demás pestañas. Pueden ser ciertas, pero tómalas con cautela. Si más medios las publican, pasan a su pestaña."));
  }
  if (cat.id === "cripto") {
    list.append(el("p", "note", "Solo noticias de criptomonedas verificadas por 3 o más medios distintos. Sin comunicados, contenido patrocinado ni predicciones de precio."));
  }
  if (cat.id === "buenas") {
    list.append(el("p", "note", "Progreso y buenas acciones de todo el mundo. Aquí basta una fuente confiable; las pistas de Reddit solo entran si un medio serio publica la nota."));
  }
  if (cat.title) list.append(el("h2", "cat-title", cat.title));
  let stories = cat.stories;
  if (cat.id === "mundo") {
    // Descripción en una línea; el resto se abre con «más info».
    const info = el("details", "note mnote");
    info.open = state.mundoInfo;
    info.addEventListener("toggle", () => { state.mundoInfo = info.open; });
    const sm = el("summary");
    sm.append("Noticias internacionales de 3 o más medios. ", el("span", "more", "más info"));
    info.append(sm, el("p", null, "Filtra por región; «General» son las de alcance mundial. La región sale de los lugares que nombran las notas y de dónde son los medios."));
    list.append(info);
    const bar = el("div", "bfilter mfilter");
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Filtrar Mundo por región");
    const opts = [{ id: "todas", label: "Todas", count: stories.length }].concat(cat.filters || []);
    if (!opts.some((o) => o.id === state.mundoFilter)) state.mundoFilter = "todas";
    opts.forEach((o) => {
      const b = el("button", "bf" + (state.mundoFilter === o.id ? " on" : "") + (o.count ? "" : " zero"));
      b.type = "button";
      b.dataset.filter = o.id;
      b.append(o.label, el("span", "count", String(o.count)));
      b.addEventListener("click", () => { state.mundoFilter = o.id; renderList(); });
      bar.append(b);
    });
    list.append(bar);
    // Fila de un solo renglón que se desliza: deja visible el filtro activo (sin mover la página).
    const onChip = bar.querySelector(".bf.on");
    if (onChip && bar.scrollWidth > bar.clientWidth) {
      bar.scrollLeft = onChip.offsetLeft - (bar.clientWidth - onChip.offsetWidth) / 2;
    }
    const f = state.mundoFilter;
    if (f === "general") stories = stories.filter((s) => s.mundoGeneral);
    else if (f !== "todas") stories = stories.filter((s) => (s.mundoRegions || []).includes(f));
    if (!stories.length) {
      const o = opts.find((x) => x.id === f);
      list.append(el("p", "empty", f === "todas"
        ? "En esta actualización ninguna noticia internacional fue publicada por 3 o más medios distintos."
        : "En esta actualización ninguna noticia de " + (f === "general" ? "alcance mundial" : o.label) + " fue publicada por 3 o más medios distintos."));
    }
  }
  if (cat.id === "buenas") {
    const nCr = stories.filter((s) => s.cr).length;
    const bar = el("div", "bfilter");
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Filtrar buenas noticias");
    [["todas", "Todas", stories.length], ["cr", "Costa Rica", nCr], ["mundo", "Mundo", stories.length - nCr]].forEach(([id, label, n]) => {
      const b = el("button", "bf" + (state.buenasFilter === id ? " on" : ""));
      b.type = "button";
      b.dataset.filter = id;
      b.append(label, el("span", "count", String(n)));
      b.addEventListener("click", () => { state.buenasFilter = id; renderList(); });
      bar.append(b);
    });
    list.append(bar);
    if (state.buenasFilter === "cr") stories = stories.filter((s) => s.cr);
    if (state.buenasFilter === "mundo") stories = stories.filter((s) => !s.cr);
    if (!stories.length) list.append(el("p", "empty", "Ahora mismo no hay buenas noticias de Costa Rica confirmadas por un medio confiable."));
  }
  renderStories(list, cat.id, stories);
  requestAnimationFrame(() => fitClamps(list));
}

// Activas arriba; las que no tienen notas nuevas en 24 h van plegadas en «Anteriores».
function renderStories(list, catId, stories) {
  const en = state.lang === "en";
  const active = stories.filter((s) => !s.stale);
  const older = stories.filter((s) => s.stale);
  active.forEach((s) => list.append(card(s)));
  if (!older.length) return;
  if (!active.length) {
    list.append(el("p", "empty", en ? "No story here has new articles in the last 24 hours."
      : "Ninguna historia de aquí tiene notas nuevas en las últimas 24 horas."));
  }
  const det = el("details", "older");
  det.open = !!state.olderOpen[catId];
  det.addEventListener("toggle", () => { state.olderOpen[catId] = det.open; if (det.open) fitClamps(det); });
  const sum = el("summary");
  sum.append(el("span", "older-title", (en ? "Earlier" : "Anteriores") + " (" + older.length + ")"),
    el("span", "older-note", en ? "no new articles in 24 h" : "sin notas nuevas en 24 h"));
  det.append(sum);
  const box = el("div", "older-list");
  older.forEach((s) => box.append(card(s)));
  det.append(box);
  list.append(det);
}

// Qué es de los medios y qué no, según lo que trae esta actualización.
function aboutText(data) {
  const all = data.categories.flatMap((c) => c.stories);
  const ia = all.some((s) => s.narrKind === "ia");
  const ex = all.some((s) => s.narrKind === "extracto");
  if (!ia && !ex) return "Los titulares y resúmenes son los de cada medio, sin cambios. No hay IA ni se inventa nada; toca una fuente para leer el original.";
  let t = "Los titulares son los de cada medio, sin cambios. ";
  if (ia) {
    const model = data.narration && data.narration.model ? " (" + data.narration.model + ")" : "";
    t += "Las descripciones marcadas «Resumen generado con IA» las escribe una IA" + model +
      " solo con los titulares y resúmenes de los medios de esa historia: no busca nada más, pero puede equivocarse u omitir algo. ";
  }
  if (ex) t += (ia ? "Las marcadas" : "Las descripciones marcadas") +
    " «Extracto» son frases copiadas de varios medios, cada una con el nombre de quien la publicó, sin IA. ";
  if (all.some((s) => !s.narrKind)) t += "Las demás muestran el resumen de un medio, tal cual. ";
  return t + "En «Ver fuentes» están los resúmenes originales y las notas; toca una para leer el original.";
}

function renderFoot(data) {
  const st = data.stats || {};
  const f = document.getElementById("foot");
  f.innerHTML = "";
  f.append(
    el("p", null, "Cómo funciona: cada 3 horas se leen " + (st.feedsOk || "?") + " canales RSS públicos (" +
      (st.itemsGathered || "?") + " notas en esta tanda). Se agrupan las notas que hablan del mismo hecho, en español o inglés, y solo se muestran los grupos que publican al menos 3 medios distintos. Más medios = más consenso. Costa Rica y los filtros por región de Mundo usan la misma regla; la región sale de los lugares que nombran las notas y de dónde son los medios. Excepción: en Buenas noticias basta un medio confiable, y lo que sale de Reddit o 9gag solo se usa como pista."),
    el("p", null, aboutText(data)),
    el("p", "small", "Medios: " + (data.sourcesUsed || []).join(", ") + ".")
  );
}

document.querySelectorAll(".lang").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.lang = btn.dataset.lang;
    document.querySelectorAll(".lang").forEach((b) => b.classList.toggle("on", b === btn));
    renderList();
  });
});

fetch("noticias.json?t=" + Date.now(), { cache: "no-store" })
  .then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then((data) => {
    state.data = data;
    if (!data.categories.some((c) => c.id === state.cat)) state.cat = data.categories[0].id;
    renderSchedule(data);
    renderFx(data);
    renderTabs();
    renderList();
    if (state.cat === "deportes") spRefresh(state.sportSel, false);
    renderFoot(data);
    if (window.NoticiasTour) window.NoticiasTour.maybeStart();
  })
  .catch(() => {
    document.getElementById("schedule").textContent = "No se pudo leer noticias.json.";
  });
