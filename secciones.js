/* ═══════════════════════════════════════════════════════════════════════════
   Estructura de 6 secciones: Hoy · Costa Rica · Mundo · Dinero · Deportes · Avances
   (plan 2026-11-17-estructura-pestanas.md; base: boceto local d5a00dd).
   Se carga DESPUÉS de app.js. app.js llama a secRenderTabs/secRenderList cuando window.SEC_ON (datos con «section»);
   con un noticias.json viejo sigue la app de pestañas de siempre.
   Usa los campos que ya calcula actualizar.py: section, facets, alsoIn, tone, conflict, twoOutlets,
   confirmed, dev; y la portada «home». Las categorías viejas siguen en noticias.json (app Android).
   Sin Modo calma y sin notificaciones: Conflictos, Sucesos y las historias sensibles van abiertos y completos.
   ═══════════════════════════════════════════════════════════════════════════ */

const SECTIONS = [
  { id: "hoy", label: "Hoy" },
  { id: "costarica", label: "Costa Rica" },
  { id: "mundo", label: "Mundo" },
  { id: "dinero", label: "Dinero" },
  { id: "deportes", label: "Deportes" },
  { id: "avances", label: "Avances" },
];
const SEC_LABEL = Object.fromEntries(SECTIONS.map((s) => [s.id, s.label]));
const FACET_LABEL = { politica: "Política", sucesos: "Sucesos", conflictos: "Conflictos", buenas: "Buenas",
  finanzas: "Finanzas", cripto: "Cripto", ciencias: "Ciencias" };
const CAT_FILTER = { politica: "politica", sucesos: "sucesos", guerras: "conflictos", finanzas: "finanzas",
  cripto: "cripto", ciencias: "ciencias", buenas: "buenas" };
const SECTION_CUT = 15;
const DEV_SHOWN = 6;
state.cat = "hoy";
const B = { secFilter: {}, showAll: {}, byId: {}, stories: [], dev: [], bySec: {}, devBySec: {}, home: null };

// ── Datos: tarjetas por sección (ya deduplicadas por actualizar.py) ─────────
function buildSections(data) {
  const seen = new Set();
  B.byId = {}; B.stories = []; B.dev = [];
  data.categories.forEach((c) => (c.stories || []).forEach((s) => {
    if (!s.section || seen.has(s.id)) return;
    seen.add(s.id);
    const regions = new Set(s.mundoRegions || []);
    (s.chips || []).forEach((ch) => regions.add(ch.id));
    const x = Object.assign({}, s, { chips: [], cr: false });
    x.bSection = s.section;
    x.bFacets = new Set(s.facets || []);
    x.bRegions = regions;
    x.bDev = !!s.dev || c.id === "posibles";
    x.bSubtopic = s.subtopic ? s : null;
    x.bTone = s.tone || "neutral";
    x.bConflict = s.conflict || (x.bFacets.has("conflictos") ? "Otros frentes" : null);
    // «También en…»: máx. 2, a otra sección (o a un filtro de la misma), con el filtro exacto.
    x.bAlsoIn = (s.alsoIn || []).filter((a) => a.section && SEC_LABEL[a.section]).slice(0, 2).map((a) => {
      const f = CAT_FILTER[a.id] || null;
      const lab = a.sameSection ? (FACET_LABEL[f] || a.label) : a.sectionLabel + (f && FACET_LABEL[f] ? " · " + FACET_LABEL[f] : "");
      return { section: a.section, facet: f, label: "También en " + lab };
    });
    B.byId[s.id] = x;
    (x.bDev ? B.dev : B.stories).push(x);
  }));
  const ord = (a, b) => (a.stale - b.stale) || (b.outlets - a.outlets) ||
    (new Date(b.lastArticle || b.lastSeen) - new Date(a.lastArticle || a.lastSeen));
  B.stories.sort(ord);
  B.dev.sort(ord);
  SECTIONS.forEach((x) => {
    B.bySec[x.id] = B.stories.filter((s) => s.bSection === x.id);
    B.devBySec[x.id] = B.dev.filter((s) => s.bSection === x.id);
  });
  B.home = homeFrom(data);
}

// Portada: la arma actualizar.py (build_home); si faltara, se compone aquí con las mismas reglas.
function homeFrom(data) {
  if (data.home && Array.isArray(data.home.blocks)) {
    const blocks = data.home.blocks.map((b) => Object.assign({}, b, {
      stories: (b.stories || []).map((id) => B.byId[id]).filter(Boolean) }));
    return { blocks, count: blocks.reduce((n, b) => n + (b.dev ? 0 : b.stories.length), 0) };
  }
  const used = new Set();
  const pick = (arr, n, pred) => {
    const out = [];
    for (const s of arr) { if (out.length >= n) break; if (s.stale || used.has(s.id) || (pred && !pred(s))) continue; used.add(s.id); out.push(s); }
    return out;
  };
  const bs = B.bySec;
  const closing = pick(B.stories.filter((s) => s.bFacets.has("buenas")), 1);
  const blocks = [
    { id: "ancla" },
    { id: "cercano", title: "Lo cercano", stories: pick(bs.costarica, 2) },
    { id: "grande", title: "Lo grande", stories: pick(bs.mundo, 2, (s) => !s.bFacets.has("conflictos")) },
    { id: "respiro", title: "Respiro", stories: pick(bs.avances, 1) },
    { id: "util", title: "Lo útil", stories: pick(bs.dinero, 1), markets: true },
    { id: "conflictos", title: "Conflictos y sucesos", stories: pick(B.stories, 3, (s) => s.bFacets.has("conflictos")).concat(pick(B.stories, 1, (s) => s.bFacets.has("sucesos"))) },
    { id: "ligero", title: "Ligero", games: true, stories: pick(bs.deportes, 1) },
    { id: "desarrollo", title: "En desarrollo", stories: B.dev.filter((s) => !s.stale).slice(0, 3), dev: true },
    { id: "cierre", title: "Para cerrar", stories: closing },
  ];
  return { blocks, count: blocks.reduce((n, b) => n + ((b.stories && !b.dev) ? b.stories.length : 0), 0) };
}

// ── Tarjetas ─────────────────────────────────────────────────────────────────
function bCard(s, opts) {
  opts = opts || {};
  const art = card(s);
  const top = art.querySelector(".cardtop");
  const first = top.firstChild;
  const add = (node) => top.insertBefore(node, first);
  if (opts.home) {
    // En Hoy: etiqueta de sección en lugar de «También en…»
    let lab = SEC_LABEL[s.bSection];
    const f = [...s.bFacets].find((x) => FACET_LABEL[x]);
    if (s.bConflict) lab += " · " + s.bConflict;
    else if (f) lab += " · " + FACET_LABEL[f];
    add(el("span", "chip seclab", lab));
  } else if (!s.bDev) {
    [...s.bFacets].filter((f) => ["politica", "sucesos", "buenas"].includes(f) && f !== B.secFilter[s.bSection])
      .forEach((f) => add(el("span", "chip facet", FACET_LABEL[f])));
  }
  const o = top.querySelector(".outlets");
  if (s.bDev) {
    if (o) o.classList.add("maybe");
    add(el("span", "chip dev", "En desarrollo"));
  }
  if (s.twoOutlets && !s.bDev) add(el("span", "chip two", "2 medios"));
  if (s.confirmed) add(el("span", "chip ok", "Confirmada ✓"));
  if (!opts.home && s.bAlsoIn.length) {
    const row = el("p", "also");
    s.bAlsoIn.forEach((a) => {
      const b = el("button", "also-chip", a.label + " ›");
      b.type = "button";
      b.addEventListener("click", () => go(a.section, a.facet || "todo"));
      row.append(b);
    });
    art.insertBefore(row, top.nextSibling);
  }
  if (s.bTone === "heavy") art.classList.add("tone-heavy");
  return art;
}

function go(sec, filter) {
  const prev = state.cat;
  state.cat = sec;
  if (filter) B.secFilter[sec] = filter;
  renderTabs(); renderList(); window.scrollTo({ top: 0 });
  if (sec === "deportes" && prev !== "deportes") spRefresh(state.sportSel, false);
  else if (sec !== "deportes") clearTimeout(spLive.timer);
}

// ── Barra de 6 secciones ─────────────────────────────────────────────────────
function secRenderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  SECTIONS.forEach((c) => {
    const b = el("button", "tab" + (c.id === state.cat ? " on" : ""));
    b.type = "button";
    b.dataset.cat = c.id;
    b.append(c.label);
    if (c.id === "hoy") b.append(el("span", "count", String(B.home.count)));
    else if (c.id === "deportes") {
      const sp = state.data.sports;
      const live = sp ? sp.leagues.reduce((n, l) => n + ((l.counts && l.counts.in) || 0), 0) : 0;
      b.append(el("span", "count" + (live ? " live" : ""), live ? live + " en juego" : String(B.bySec.deportes.length)));
    } else b.append(el("span", "count", String(B.bySec[c.id].length)));
    b.addEventListener("click", () => go(c.id));
    nav.appendChild(b);
  });
}

function filterBar(sec, opts) {
  const bar = el("div", "bfilter mfilter");
  bar.setAttribute("role", "group");
  if (!opts.some((o) => o.id === B.secFilter[sec])) B.secFilter[sec] = "todo";
  opts.forEach((o) => {
    const b = el("button", "bf" + (B.secFilter[sec] === o.id ? " on" : "") + (o.count ? "" : " zero"));
    b.type = "button";
    b.setAttribute("aria-pressed", String(B.secFilter[sec] === o.id));
    b.append(o.label, el("span", "count", String(o.count)));
    b.addEventListener("click", () => { B.secFilter[sec] = o.id; renderList(); });
    bar.append(b);
  });
  return bar;
}

function sectionCut(list, sec, stories, label) {
  const active = stories.filter((s) => !s.stale);
  const older = stories.filter((s) => s.stale);
  const shown = B.showAll[sec] ? active : active.slice(0, SECTION_CUT);
  if (!active.length) list.append(el("p", "empty", "Ahora mismo no hay historias activas aquí."));
  shown.forEach((s) => list.append(bCard(s)));
  const end = el("div", "sec-end");
  end.append(el("p", "sec-end-t", "Hasta aquí lo principal de " + label + " · ✓ al día"));
  if (active.length > shown.length) {
    const more = el("button", "bf", "Ver " + (active.length - shown.length) + " más");
    more.type = "button";
    more.addEventListener("click", () => { B.showAll[sec] = true; renderList(); });
    end.append(more);
  }
  list.append(end);
  if (older.length) {
    // «Anteriores» = sin notas nuevas en 24 h (frescura), no un filtro de contenido.
    const det = el("details", "older");
    det.open = !!state.olderOpen[sec];
    det.addEventListener("toggle", () => { state.olderOpen[sec] = det.open; if (det.open) fitClamps(det); });
    const sum = el("summary");
    sum.append(el("span", "older-title", "Anteriores (" + older.length + ")"), el("span", "older-note", "sin notas nuevas en 24 h"));
    det.append(sum);
    const box = el("div", "older-list");
    older.forEach((s) => box.append(bCard(s)));
    det.append(box);
    list.append(det);
  }
}

function devBlock(list, sec, all) {
  const dev = B.devBySec[sec] || [];
  if (!dev.length) return;
  list.append(el("h2", "blk-title dev-title", "En desarrollo · " + dev.length));
  list.append(el("p", "note warn", "2 medios, aún sin un tercero que lo confirme. Si se confirma, sube a la sección con «Confirmada ✓»; si no, desaparece en 48 h."));
  const shown = all || B.showAll["dev:" + sec] ? dev : dev.slice(0, DEV_SHOWN);
  shown.forEach((s) => list.append(bCard(s)));
  if (dev.length > shown.length) {
    const more = el("button", "bf", "Ver " + (dev.length - shown.length) + " más en desarrollo");
    more.type = "button";
    more.addEventListener("click", () => { B.showAll["dev:" + sec] = true; renderList(); });
    list.append(more);
  }
}

function blockTitle(list, t, sub) {
  const h = el("div", "blk-head");
  h.append(el("h2", "blk-title", t));
  if (sub) h.append(el("span", "blk-sub", sub));
  list.append(h);
}

// ── Pintado por sección ──────────────────────────────────────────────────────
function secRenderList() {
  const list = document.getElementById("list");
  list.innerHTML = "";
  list.dataset.sec = state.cat;
  document.querySelector(".langs").style.display = state.cat === "deportes" ? "none" : "";
  ({ hoy: renderHoy, costarica: renderCR, mundo: renderMundo, dinero: renderDinero, deportes: renderDeportes, avances: renderAvances })[state.cat](list);
  requestAnimationFrame(() => fitClamps(list));
}

const hoyFmt = new Intl.DateTimeFormat("es-CR", { timeZone: TZ, weekday: "long", day: "numeric" });
const hhmm = new Intl.DateTimeFormat("es-CR", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false });

function renderHoy(list) {
  const d = state.data;
  B.home.blocks.forEach((b) => {
    if (b.id === "ancla") {
      const a = el("section", "ancla");
      a.append(el("p", "ancla-t", "Hoy, " + hoyFmt.format(new Date(d.updatedAt)) + " · actualizado " + hhmm.format(new Date(d.updatedAt)) + " (hora CR) · " + B.home.count + " historias"));
      a.append(el("p", "ancla-s", "Una lectura corta, con principio y final."));
      list.append(a);
      return;
    }
    if (b.markets) {
      blockTitle(list, b.title, "mercados y una de Dinero");
      list.append(miniMarkets());
      b.stories.forEach((s) => list.append(bCard(s, { home: true })));
      return;
    }
    if (b.games) {
      const games = topGames(3);
      if (!games.length && !b.stories.length) return;
      blockTitle(list, b.title, "Deportes");
      if (games.length) {
        const box = el("section", "mini-games");
        games.forEach(([g, lg]) => box.append(gameCard(g, lg)));
        list.append(box);
      }
      b.stories.forEach((s) => list.append(bCard(s, { home: true })));
      const a = el("button", "also-chip", "Ver todo en Deportes ›"); a.type = "button"; a.addEventListener("click", () => go("deportes"));
      list.append(a);
      return;
    }
    if (b.id === "cierre") {
      if (b.stories.length) {
        blockTitle(list, "Para cerrar", "la mejor buena noticia del día");
        b.stories.forEach((s) => { const c = bCard(s, { home: true }); c.classList.add("closing"); list.append(c); });
      }
      const end = el("section", "aldia");
      end.append(el("p", "aldia-t", "✓ Estás al día"));
      end.append(el("p", "aldia-s", "Próxima actualización a las " + hhmm.format(new Date(d.nextRefreshAt)) + " (hora CR)"));
      const nav = el("div", "aldia-nav");
      SECTIONS.filter((x) => x.id !== "hoy").forEach((x) => {
        const bt = el("button", "bf", x.label); bt.type = "button"; bt.addEventListener("click", () => go(x.id)); nav.append(bt);
      });
      end.append(nav);
      list.append(end);
      return;
    }
    if (!b.stories || !b.stories.length) return;
    blockTitle(list, b.title, b.dev ? "2 medios, sin confirmar" : null);
    b.stories.forEach((s) => list.append(bCard(s, { home: true })));
    if (b.dev) {
      const bt = el("button", "also-chip", "Ver todo lo en desarrollo (" + B.dev.length + ") ›"); bt.type = "button";
      bt.addEventListener("click", () => go("mundo", "dev"));
      list.append(bt);
    }
  });
}

function miniMarkets() {
  const d = state.data;
  const box = el("section", "mini-mk cx");
  const coins = (d.cryptoPrices && d.cryptoPrices.coins || []).filter((c) => ["BTC", "ETH"].includes(c.symbol));
  coins.forEach((c) => {
    const cell = el("div", "mk-cell" + trend(c.change24h));
    cell.append(el("span", "mk-l", c.symbol), el("span", "mk-v", usdFmt(c.price)), el("span", "mk-c cx-chg" + trend(c.change24h), pctFmt(c.change24h) + " 24 h"));
    box.append(cell);
  });
  if (d.exchange && d.exchange.dolar) {
    const x = d.exchange.dolar;
    const cell = el("div", "mk-cell");
    cell.append(el("span", "mk-l", "Dólar venta"), el("span", "mk-v", crc(x.venta)), el("span", "mk-c", x.cambioVenta ? (x.cambioVenta > 0 ? "▲ " : "▼ ") + crc(Math.abs(x.cambioVenta)) : "= sin cambio"));
    box.append(cell);
  }
  return box;
}

function topGames(n) {
  const sp = state.data.sports;
  if (!sp || !sp.leagues) return [];
  const out = [];
  sp.leagues.forEach((lg) => lg.games.filter((g) => g.state === "post" && lg.id !== "tenis").slice(0, 1).forEach((g) => out.push([g, lg])));
  return out.slice(0, n);
}

function renderCR(list) {
  const all = B.bySec.costarica;
  const dev = B.devBySec.costarica;
  const by = (f) => all.filter((s) => s.bFacets.has(f));
  list.append(el("p", "note", "País, política nacional, sucesos y buenas noticias ticas, todo abierto."));
  list.append(filterBar("costarica", [
    { id: "todo", label: "Todo", count: all.length }, { id: "politica", label: "Política", count: by("politica").length },
    { id: "sucesos", label: "Sucesos", count: by("sucesos").length }, { id: "buenas", label: "Buenas", count: by("buenas").length },
    { id: "dev", label: "En desarrollo", count: dev.length }]));
  const f = B.secFilter.costarica;
  if (f === "dev") { devBlock(list, "costarica", true); return; }
  sectionCut(list, "costarica", f === "todo" ? all : by(f), "Costa Rica");
  devBlock(list, "costarica");
}

// Conflictos agrupados por frente, abiertos y completos (sin plegar ni resumir).
function conflictBlock(list, stories) {
  const fronts = {};
  stories.forEach((s) => { (fronts[s.bConflict] = fronts[s.bConflict] || []).push(s); });
  const order = Object.keys(fronts).sort((a, b) => (a === "Otros frentes") - (b === "Otros frentes") || fronts[b].length - fronts[a].length);
  blockTitle(list, "Conflictos", stories.length + " historias · agrupadas por frente");
  order.forEach((fr) => {
    const ss = fronts[fr];
    const box = el("section", "frente");
    box.append(el("h3", "frente-t", fr + " · " + ss.length));
    list.append(box);
    ss.forEach((s) => list.append(bCard(s)));
  });
}

function renderMundo(list) {
  const all = B.bySec.mundo;
  const regs = (state.data.categories.find((c) => c.id === "mundo") || {}).filters || [];
  const conf = all.filter((s) => s.bFacets.has("conflictos"));
  const opts = [{ id: "todo", label: "Todo", count: all.length },
    { id: "conflictos", label: "Conflictos", count: conf.length },
    { id: "politica", label: "Política int.", count: all.filter((s) => s.bFacets.has("politica")).length },
    { id: "sucesos", label: "Sucesos", count: all.filter((s) => s.bFacets.has("sucesos")).length }]
    .concat(regs.map((r) => ({ id: "r:" + r.id, label: r.label,
      count: all.filter((s) => (r.id === "general" ? s.mundoGeneral : s.bRegions.has(r.id))).length })))
    .concat([{ id: "dev", label: "En desarrollo", count: B.dev.length }]);
  list.append(el("p", "note", "Regiones, política internacional, Conflictos y sucesos internacionales, todo abierto."));
  list.append(filterBar("mundo", opts));
  const f = B.secFilter.mundo;
  if (f === "dev") {   // todo lo en desarrollo de todas las secciones (pie de Hoy)
    SECTIONS.filter((x) => x.id !== "hoy" && B.devBySec[x.id].length).forEach((x) => {
      blockTitle(list, x.label);
      devBlock(list, x.id, true);
    });
    return;
  }
  if (f === "conflictos") { conflictBlock(list, conf); return; }
  if (f === "todo") {
    const rest = all.filter((s) => !s.bFacets.has("conflictos"));
    const top = rest.filter((s) => !s.stale).slice(0, 6);
    top.forEach((s) => list.append(bCard(s)));
    if (conf.length) conflictBlock(list, conf);
    blockTitle(list, "Más de Mundo");
    sectionCut(list, "mundo", rest.filter((s) => !top.includes(s)), "Mundo");
    devBlock(list, "mundo");
    return;
  }
  let ss;
  if (f.startsWith("r:")) { const r = f.slice(2); ss = all.filter((s) => (r === "general" ? s.mundoGeneral : s.bRegions.has(r))); }
  else ss = all.filter((s) => s.bFacets.has(f));
  sectionCut(list, "mundo", ss, "Mundo");
}

function renderDinero(list) {
  // Primero los precios: cripto y tipo de cambio; luego las noticias.
  blockTitle(list, "Mercados", "primero los precios");
  renderCrypto(list);
  const fxBox = document.getElementById("fx");
  if (fxBox && fxBox.childNodes.length) { const c = fxBox.cloneNode(true); c.id = "fx-dinero"; c.hidden = false; c.classList.add("fx-in"); list.append(c); }
  const all = B.bySec.dinero;
  blockTitle(list, "Noticias", "Finanzas y Cripto");
  list.append(filterBar("dinero", [{ id: "todo", label: "Todo", count: all.length },
    { id: "finanzas", label: "Finanzas", count: all.filter((s) => s.bFacets.has("finanzas")).length },
    { id: "cripto", label: "Cripto", count: all.filter((s) => s.bFacets.has("cripto")).length }]));
  const f = B.secFilter.dinero;
  sectionCut(list, "dinero", f === "todo" ? all : all.filter((s) => s.bFacets.has(f)), "Dinero");
  devBlock(list, "dinero");
}

function renderDeportes(list) {
  renderSports(list);
  blockTitle(list, "Noticias deportivas", "3 o más medios");
  sectionCut(list, "deportes", B.bySec.deportes, "Deportes");
  devBlock(list, "deportes");
}

function renderAvances(list) {
  const all = B.bySec.avances;
  const subs = {};
  all.forEach((s) => { if (s.subtopic) { subs[s.subtopic] = subs[s.subtopic] || { label: s.subtopicLabel, n: 0 }; subs[s.subtopic].n++; } });
  list.append(el("p", "note", "Buenas noticias y ciencia con evidencia. Las buenas noticias ticas viven en Costa Rica, con «También en Avances»."));
  list.append(filterBar("avances", [{ id: "todo", label: "Todo", count: all.length },
    { id: "ciencias", label: "Ciencias", count: all.filter((s) => s.bFacets.has("ciencias")).length }]
    .concat(Object.entries(subs).map(([k, v]) => ({ id: "st:" + k, label: v.label, count: v.n })))));
  const f = B.secFilter.avances;
  let ss = all;
  if (f === "ciencias" || f === "buenas") ss = all.filter((s) => s.bFacets.has(f));
  else if (f.startsWith("st:")) ss = all.filter((s) => s.subtopic === f.slice(3));
  sectionCut(list, "avances", ss, "Avances");
  devBlock(list, "avances");
}

// Encabezado: una línea con el dólar; el cuadro completo vive en Dinero.
function renderFxCompact(data) {
  const box = document.getElementById("fxline");
  if (!box || !data.exchange || !data.exchange.dolar) return;
  const x = data.exchange.dolar;
  box.textContent = "Dólar BCCR · compra " + crc(x.compra) + " · venta " + crc(x.venta);
}

// Arranque (lo llama app.js tras leer noticias.json). Sin «section» en los datos (json viejo) → app de pestañas.
function seccionesInit(data) {
  if (!data.categories.some((c) => (c.stories || []).some((s) => s.section))) return false;
  buildSections(data);
  window.SEC_ON = true;
  document.getElementById("tabs").setAttribute("aria-label", "Secciones");
  const fx = document.getElementById("fx");
  if (fx) fx.hidden = true;
  renderFxCompact(data);
  const q = new URLSearchParams(location.search);
  if (q.get("s") && SEC_LABEL[q.get("s")]) state.cat = q.get("s");
  if (q.get("f")) B.secFilter[state.cat] = q.get("f");
  return true;
}
