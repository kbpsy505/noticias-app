const TZ = "America/Costa_Rica";
const when = new Intl.DateTimeFormat("es-CR", {
  timeZone: TZ, weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
});
const state = { data: null, cat: "sucesos", lang: "all" };

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

function renderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  state.data.categories.forEach((c) => {
    const b = el("button", "tab" + (c.id === state.cat ? " on" : ""));
    b.type = "button";
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

function textBlock(lang, headline, summary, summarySource, primary) {
  const wrap = el("div", "txt " + (primary ? "primary" : "secondary"));
  if (headline) {
    const h = el(primary ? "h2" : "h3");
    if (!primary || state.lang === "all") h.append(el("span", "badge " + lang, lang.toUpperCase()), " ");
    h.append(headline);
    wrap.append(h);
  }
  if (summary) {
    const p = el("p", "summary", summary);
    if (summarySource) p.append(el("span", "via", " — " + summarySource));
    wrap.append(p);
  }
  return wrap;
}

function card(s) {
  const art = el("article", "card");
  const top = el("div", "cardtop");
  const badge = el("span", "outlets" + (s.outlets >= 5 ? " hot" : ""), s.outlets + " medios");
  top.append(badge, el("span", "time", rel(s.lastSeen)));
  art.append(top);

  const es = { h: s.headlineEs, s: s.summaryEs, src: s.summaryEsSource };
  const en = { h: s.headlineEn, s: s.summaryEn, src: s.summaryEnSource };
  let order;
  if (state.lang === "en") order = en.h ? [["en", en]] : [["es", es]];
  else if (state.lang === "es") order = es.h ? [["es", es]] : [["en", en]];
  else order = [["es", es], ["en", en]].filter(([, v]) => v.h);
  order.forEach(([lang, v], i) => art.append(textBlock(lang, v.h, v.s, v.src, i === 0)));

  const det = el("details", "sources");
  const sum = el("summary", null, "Ver fuentes (" + s.sources.length + " notas en " + s.outlets + " medios)");
  det.append(sum);
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
  return art;
}

function renderList() {
  const list = document.getElementById("list");
  list.innerHTML = "";
  const cat = state.data.categories.find((c) => c.id === state.cat);
  if (!cat || !cat.stories.length) {
    list.append(el("p", "empty", "Ahora mismo no hay historias en esta categoría que publiquen 2 o más medios."));
    return;
  }
  cat.stories.forEach((s) => list.append(card(s)));
}

function renderFoot(data) {
  const st = data.stats || {};
  const f = document.getElementById("foot");
  f.innerHTML = "";
  f.append(
    el("p", null, "Cómo funciona: cada 3 horas se leen " + (st.feedsOk || "?") + " canales RSS públicos (" +
      (st.itemsGathered || "?") + " notas en esta tanda). Se agrupan las notas que hablan del mismo hecho, en español o inglés, y solo se muestran los grupos que publican al menos 2 medios distintos. Más medios = más consenso."),
    el("p", null, "Los titulares y resúmenes son los de cada medio, sin cambios. No hay IA ni se inventa nada; toca una fuente para leer el original."),
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
    renderTabs();
    renderList();
    renderFoot(data);
  })
  .catch(() => {
    document.getElementById("schedule").textContent = "No se pudo leer noticias.json.";
  });
