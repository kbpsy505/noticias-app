const TZ = "America/Costa_Rica";
const when = new Intl.DateTimeFormat("es-CR", {
  timeZone: TZ, weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
});
const state = { data: null, cat: "buenas", lang: "all", buenasFilter: "todas", mundoFilter: "todas", mundoInfo: false, olderOpen: {} };

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

function renderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  state.data.categories.forEach((c) => {
    const b = el("button", "tab" + (c.id === state.cat ? " on" : ""));
    b.type = "button";
    b.dataset.cat = c.id;
    b.append(c.label, el("span", "count", String(c.stories.length)));
    b.addEventListener("click", () => {
      state.cat = c.id;
      renderTabs();
      renderList();
      window.scrollTo({ top: 0 });
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
    renderFoot(data);
    if (window.NoticiasTour) window.NoticiasTour.maybeStart();
  })
  .catch(() => {
    document.getElementById("schedule").textContent = "No se pudo leer noticias.json.";
  });
