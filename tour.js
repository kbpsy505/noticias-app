// Tour de bienvenida: se muestra solo en la primera visita y se puede repetir con el botón "?".
(function () {
  const KEY = "noticias_tour_v1";
  const STEPS = [
    {
      title: "¡Hola! 👋",
      text: "Este es un resumen de noticias armado con el consenso de muchos medios. Se actualiza solo cada 3 horas, así que no tienes que visitar cada sitio.",
    },
    {
      target: "#tabs",
      title: "Pestañas",
      text: "Desliza hacia los lados para ver los temas: Costa Rica, Finanzas, Cripto, Política, Ciencias, Mundo (con filtros por región: Europa, Asia…), Guerras y más. La app abre en Buenas noticias. El número de cada pestaña es cuántas historias tiene.",
      onShow: () => scrollTabTo(".tab.on"),
    },
    {
      target: "#list .card .outlets",
      title: "Cuántos medios",
      text: "Esta etiqueta dice cuántos medios distintos publicaron la historia. En casi todas las pestañas solo aparecen las que publican 5 o más. En Buenas noticias basta 1 medio confiable, y ahí se ve su nombre.",
    },
    {
      target: "#list .card",
      title: "Cada historia",
      text: "Titular y resumen tal como los publicó el medio, en español y/o inglés (cámbialo con Ambos · Español · English). Toca «Ver fuente» o «Ver fuentes» para leer las notas originales.",
      tall: true,
    },
    {
      target: '.tab[data-cat="posibles"]',
      title: "Posibles noticias",
      text: "Aquí van las historias que publican solo 2 a 4 medios. Todavía no están confirmadas: tómalas con cautela. Si más medios las publican, pasan a su pestaña.",
      onShow: () => scrollTabTo('.tab[data-cat="posibles"]'),
      onHide: () => scrollTabTo(".tab.on"),
    },
    {
      target: "#schedule",
      title: "Siempre al día",
      text: "Aquí ves la hora de la última actualización y de la próxima (cada 3 horas, hora de Costa Rica). Justo abajo está el tipo de cambio del dólar y el euro. Para ver este tour otra vez, toca el botón «?» de arriba.",
      extra: "#tourBtn",
    },
  ];

  let i = 0, ov, spot, tip, onMove;

  function scrollTabTo(sel) {
    const t = document.querySelector(sel);
    const nav = document.getElementById("tabs");
    if (!t || !nav) return;
    nav.scrollLeft = t.offsetLeft - (nav.clientWidth - t.offsetWidth) / 2;
  }

  function visible(e) {
    if (!e) return false;
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function build() {
    ov = document.createElement("div");
    ov.className = "tour-ov";
    spot = document.createElement("div");
    spot.className = "tour-spot";
    tip = document.createElement("div");
    tip.className = "tour-tip";
    tip.setAttribute("role", "dialog");
    tip.setAttribute("aria-modal", "true");
    tip.setAttribute("aria-live", "polite");
    ov.addEventListener("click", (e) => e.stopPropagation());
    document.body.append(ov, spot, tip);
    onMove = () => place();
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, { passive: true });
    document.addEventListener("keydown", onKey);
    document.documentElement.classList.add("tour-open");
  }

  function onKey(e) {
    if (e.key === "Escape") end();
    else if (e.key === "ArrowRight") go(1);
    else if (e.key === "ArrowLeft") go(-1);
  }

  function current() {
    const s = STEPS[i];
    const t = s.target ? document.querySelector(s.target) : null;
    return { s, t: visible(t) ? t : null };
  }

  function render() {
    const { s, t } = current();
    tip.innerHTML = "";
    const h = document.createElement("h3");
    h.textContent = s.title;
    const p = document.createElement("p");
    p.textContent = s.text;
    const bar = document.createElement("div");
    bar.className = "tour-bar";
    const skip = btn("Saltar", "tour-skip", end);
    const count = document.createElement("span");
    count.className = "tour-count";
    count.textContent = (i + 1) + " de " + STEPS.length;
    const back = btn("Atrás", "tour-back", () => go(-1));
    back.disabled = i === 0;
    const last = i === STEPS.length - 1;
    const next = btn(last ? "¡Listo!" : "Siguiente", "tour-next", () => (last ? end() : go(1)));
    const nav = document.createElement("span");
    nav.className = "tour-nav";
    nav.append(back, next);
    bar.append(skip, count, nav);
    tip.append(h, p, bar);
    document.querySelectorAll(".tour-glow").forEach((e) => e.classList.remove("tour-glow"));
    if (s.extra) {
      const x = document.querySelector(s.extra);
      if (x) x.classList.add("tour-glow");
    }
    if (t) {
      const r = t.getBoundingClientRect();
      const vh = window.innerHeight;
      // Elemento alto (una tarjeta): se alinea arriba; si no, al centro.
      if (r.top < 70 || r.bottom > vh - 20) {
        t.scrollIntoView({ block: s.tall || r.height > vh * 0.5 ? "start" : "center" });
        if (s.tall) window.scrollBy(0, -70);
      }
    } else if (s.extra) {
      window.scrollTo({ top: 0 });
    }
    place();
    next.focus({ preventScroll: true });
  }

  function btn(label, cls, fn) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.textContent = label;
    b.addEventListener("click", fn);
    return b;
  }

  function place() {
    if (!tip) return;
    const { t } = current();
    const vw = document.documentElement.clientWidth, vh = window.innerHeight, pad = 6, m = 10;
    const tw = Math.min(360, vw - 2 * m);
    tip.style.width = tw + "px";
    const th = tip.offsetHeight;
    if (!t) {
      // Sin elemento (p. ej. pestaña vacía) o paso de bienvenida: todo oscuro y tooltip centrado.
      spot.style.display = "none";
      ov.classList.add("dark");
      tip.style.left = (vw - tw) / 2 + "px";
      tip.style.top = Math.max(m, (vh - th) / 2) + "px";
      return;
    }
    ov.classList.remove("dark");
    const r = t.getBoundingClientRect();
    const top = Math.max(0, r.top - pad), left = Math.max(0, r.left - pad);
    const bottom = Math.min(vh, r.bottom + pad), right = Math.min(vw, r.right + pad);
    Object.assign(spot.style, {
      display: "block", top: top + "px", left: left + "px",
      width: Math.max(0, right - left) + "px", height: Math.max(0, bottom - top) + "px",
    });
    let y;
    if (vh - bottom >= th + m) y = bottom + m;          // debajo
    else if (top >= th + m) y = top - th - m;           // encima
    else y = vh - th - m;                                // no cabe: abajo, sobre el elemento
    const cx = (left + right) / 2;
    tip.style.left = Math.min(Math.max(m, cx - tw / 2), vw - tw - m) + "px";
    tip.style.top = Math.max(m, y) + "px";
  }

  function go(d) {
    const s = STEPS[i];
    if (s.onHide) s.onHide();
    i = Math.min(STEPS.length - 1, Math.max(0, i + d));
    if (STEPS[i].onShow) STEPS[i].onShow();
    render();
  }

  function end() {
    if (STEPS[i] && STEPS[i].onHide) STEPS[i].onHide();
    try { localStorage.setItem(KEY, "1"); } catch (e) { /* modo privado */ }
    window.removeEventListener("resize", onMove);
    window.removeEventListener("scroll", onMove);
    document.removeEventListener("keydown", onKey);
    document.querySelectorAll(".tour-glow").forEach((e) => e.classList.remove("tour-glow"));
    [ov, spot, tip].forEach((e) => e && e.remove());
    ov = spot = tip = null;
    document.documentElement.classList.remove("tour-open");
    const b = document.getElementById("tourBtn");
    if (b) b.focus({ preventScroll: true });
  }

  function start() {
    if (tip) return;
    i = 0;
    window.scrollTo({ top: 0 });
    build();
    render();
  }

  window.NoticiasTour = {
    start,
    // Se llama desde app.js cuando ya están las pestañas y las tarjetas.
    maybeStart() {
      let seen = false;
      try { seen = localStorage.getItem(KEY) === "1"; } catch (e) { seen = true; }
      if (!seen) setTimeout(start, 350);
    },
  };

  const b = document.getElementById("tourBtn");
  if (b) b.addEventListener("click", start);
})();
