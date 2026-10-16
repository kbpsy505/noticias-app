const TZ = "America/Costa_Rica";
const when = new Intl.DateTimeFormat("es-CR", {
  timeZone: TZ,
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});

const state = { data: null, cat: "sucesos", lang: "all" };

function fmt(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return when.format(d) + " CR";
}

function rel(iso) {
  const d = new Date(iso);
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (Number.isNaN(mins)) return "";
  if (mins < 1) return "ahora";
  if (mins < 60) return "hace " + mins + " min";
  const h = Math.round(mins / 60);
  if (h < 36) return "hace " + h + " h";
  const days = Math.round(h / 24);
  return "hace " + days + " d";
}

function renderSchedule(data) {
  const el = document.getElementById("schedule");
  const next = new Date(data.nextRefreshAt);
  const late = !Number.isNaN(next.getTime()) && Date.now() > next.getTime();
  el.innerHTML =
    "<strong>Última actualización:</strong> " + fmt(data.updatedAt) +
    "<br><strong>Próxima descarga:</strong> " + fmt(data.nextRefreshAt) +
    (late ? '<br><span class="due">Pendiente: ya toca volver a descargar. Estos son los últimos titulares reales guardados.</span>' : "");
}

function renderTabs(data) {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  data.categories.forEach((c) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tab" + (c.id === state.cat ? " on" : "");
    b.textContent = c.label;
    b.addEventListener("click", () => {
      state.cat = c.id;
      renderTabs(data);
      renderList();
    });
    nav.appendChild(b);
  });
}

function renderList() {
  const data = state.data;
  const list = document.getElementById("list");
  const items = data.items.filter((it) => {
    if (it.category !== state.cat) return false;
    if (state.lang !== "all" && it.lang !== state.lang) return false;
    return true;
  });
  if (!items.length) {
    list.innerHTML = '<p class="empty">No hay titulares en este filtro con la última descarga.</p>';
    return;
  }
  list.innerHTML = "";
  items.forEach((it) => {
    const card = document.createElement("article");
    card.className = "card";
    const h2 = document.createElement("h2");
    const a = document.createElement("a");
    a.href = it.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = it.title;
    h2.appendChild(a);
    const meta = document.createElement("div");
    meta.className = "meta";
    const src = document.createElement("span");
    src.className = "source";
    src.textContent = it.source;
    const badge = document.createElement("span");
    badge.className = "badge " + it.lang;
    badge.textContent = it.lang === "es" ? "ES" : "EN";
    const time = document.createElement("span");
    time.textContent = rel(it.publishedAt) + " · " + fmt(it.publishedAt);
    meta.append(src, badge, time);
    card.append(h2, meta);
    list.appendChild(card);
  });
}

function renderFoot(data) {
  const names = (data.sourcesUsed || []).join(", ");
  document.getElementById("foot").textContent =
    "Fuentes de esta descarga: " + names +
    ". Cada titular enlaza al medio original. No se inventan noticias. Para traer otra tanda, ejecuta actualizar.py (cada 3 horas).";
}

document.querySelectorAll(".lang").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.lang = btn.dataset.lang;
    document.querySelectorAll(".lang").forEach((b) => b.classList.toggle("on", b === btn));
    renderList();
  });
});

fetch("noticias.json", { cache: "no-store" })
  .then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then((data) => {
    state.data = data;
    if (!data.categories.some((c) => c.id === state.cat) && data.categories[0]) {
      state.cat = data.categories[0].id;
    }
    renderSchedule(data);
    renderTabs(data);
    renderList();
    renderFoot(data);
  })
  .catch(() => {
    document.getElementById("schedule").textContent = "No se pudo leer noticias.json.";
    document.getElementById("list").innerHTML =
      '<p class="err">Abre esta carpeta con un servidor local, no como archivo suelto. En la carpeta del prototipo: python3 -m http.server 8080</p>';
  });
