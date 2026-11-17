// Pruebas del criterio de render (sin jsdom). Demuestran la política segura de texto
// y prueban el safeHttpUrl() real de app.js.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import assert from "node:assert/strict";

const here = path.dirname(fileURLToPath(import.meta.url));
const appJs = readFileSync(path.join(here, "../../app.js"), "utf8");

// Réplica de el() en app.js:25 — el texto va a textContent, no se parsea como HTML.
function el(tag, cls, text) {
  const e = { tagName: tag, className: cls || "", textContent: "", childNodes: [] };
  if (text != null) e.textContent = String(text);
  e.append = (...nodes) => { e.childNodes.push(...nodes); return e; };
  return e;
}

// safeHttpUrl() se extrae de app.js y se evalúa aislada (sin DOM).
const m = appJs.match(/function safeHttpUrl\(u\) \{[\s\S]*?\n\}\n/);
if (!m) throw new Error("app.js debe definir safeHttpUrl(u)");
const safeHttpUrl = new Function(m[0] + "; return safeHttpUrl;")();

test("el() guarda HTML malicioso como texto, no como nodos", () => {
  const e = el("p", "summary", "<img src=x onerror=alert(1)>");
  assert.equal(e.textContent, "<img src=x onerror=alert(1)>");
  assert.equal(e.childNodes.length, 0);
});

test("app.js usa textContent en el helper el()", () => {
  assert.match(appJs, /if \(text != null\) e\.textContent = text;/);
});

test("app.js solo asigna innerHTML a string vacía", () => {
  const assigns = [...appJs.matchAll(/\.innerHTML\s*=\s*([^;]+)/g)].map((m) => m[1].trim());
  assert.ok(assigns.length > 0);
  for (const expr of assigns) assert.equal(expr, '""');
});

test("safeHttpUrl de app.js rechaza javascript:, data: y sin host", () => {
  assert.equal(safeHttpUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpUrl("data:text/html,x"), null);
  assert.equal(safeHttpUrl("file:///etc/passwd"), null);
  assert.equal(safeHttpUrl("http:javascript:alert(1)"), null);
  assert.equal(safeHttpUrl("https:evil"), null);
  assert.equal(safeHttpUrl(" //evil.example/x"), null);
  assert.equal(safeHttpUrl(undefined), null);
  assert.ok(safeHttpUrl("https://example.com/nota").startsWith("https://example.com/"));
});

test("app.js no asigna .href directo: todo pasa por setHref (incluido ESPN)", () => {
  const direct = [...appJs.matchAll(/\b(\w+)\.href = ([^;]+);/g)].map((x) => x[0]);
  assert.deepEqual(direct, ["a.href = safe;"]);
  assert.match(appJs, /setHref\(a, g\.link\)/);
  assert.match(appJs, /setHref\(a, x\.url\)/);
});

// Estructura de 6 secciones (secciones.js): misma política segura de texto y enlaces.
const secJs = readFileSync(path.join(here, "../../secciones.js"), "utf8");

test("secciones.js solo asigna innerHTML a string vacía y no asigna .href", () => {
  const assigns = [...secJs.matchAll(/\.innerHTML\s*=\s*([^;]+)/g)].map((m) => m[1].trim());
  for (const expr of assigns) assert.equal(expr, '""');
  assert.equal([...secJs.matchAll(/\.href\s*=/g)].length, 0);
  assert.doesNotMatch(secJs, /insertAdjacentHTML|outerHTML|document\.write|eval\(/);
});

test("secciones: abre en Hoy, 6 secciones, sin Modo calma ni notificaciones", () => {
  assert.match(secJs, /state\.cat = "hoy";/);
  const ids = [...secJs.matchAll(/\{ id: "(\w+)", label: "[^"]+" \}/g)].slice(0, 6).map((m) => m[1]);
  assert.deepEqual(ids, ["hoy", "costarica", "mundo", "dinero", "deportes", "avances"]);
  assert.match(secJs, /✓ Estás al día/);
  const code = (secJs + appJs).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(code, /Notification|serviceWorker|pushManager|calma/i);
});

test("index.html carga secciones.js después de app.js y el tour usa la clave v2", () => {
  const html = readFileSync(path.join(here, "../../index.html"), "utf8");
  assert.ok(html.indexOf('src="secciones.js"') > html.indexOf('src="app.js"'));
  const tour = readFileSync(path.join(here, "../../tour.js"), "utf8");
  assert.match(tour, /noticias_tour_v2/);
});
