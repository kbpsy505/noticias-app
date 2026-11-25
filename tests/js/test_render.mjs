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

// Parser de sismos (RSS de la RSN) y CSP del encabezado.
const sisFn = appJs.match(/function sisParseRss\(xmlText\) \{[\s\S]*?\n\}\n/);
if (!sisFn) throw new Error("app.js debe definir sisParseRss(xmlText)");
const sisSrc = appJs.match(/function sisClean[\s\S]*function sisParseRss\(xmlText\) \{[\s\S]*?\n\}\n/)[0];
const sisParseRss = new Function(
  "const SIS_MAX = 8; const SIS_MONTHS = { enero:1,febrero:2,marzo:3,abril:4,mayo:5,junio:6,julio:7,agosto:8,septiembre:9,setiembre:9,octubre:10,noviembre:11,diciembre:12 };"
  + sisSrc + "; return sisParseRss;"
)();
const sisXml = readFileSync(path.join(here, "../fixtures/rsn-ultimos-sismos.xml"), "utf8");

test("sisParseRss lee sismos sentidos en Mw y descarta los demás", () => {
  const evs = sisParseRss(sisXml);
  assert.equal(evs.length, 3);
  assert.equal(evs[0].magnitude, 4.1);
  assert.equal(evs[0].magnitudeType, "Mw");
  assert.equal(evs[0].depthKm, 4);
  assert.equal(evs[0].latitude, 10.253);
  assert.equal(evs[0].longitude, -84.374);
  assert.equal(evs[0].felt, true);
  assert.equal(evs[0].feltIn, "Ciudad Quesada, Zarcero y Bajos del Toro");
  assert.equal(evs[0].location, "5 km al Noreste de Tapesco, Zarcero");
  assert.ok(evs[0].url.startsWith("https://rsn.ucr.ac.cr/"));
  assert.ok(evs[0].occurredAt.startsWith("2026-11-25T16:14:00"));
  assert.equal(evs[1].magnitude, 3.7);
  assert.ok(evs.every((e) => e.felt && e.magnitudeType === "Mw"));
  assert.ok(!evs.some((e) => (e.location || "").includes("Cabo Blanco")));
  assert.ok(!evs.some((e) => e.magnitude === 3.1));
  assert.ok(!evs.some((e) => (e.url || "").startsWith("javascript:")));
});

test("index.html permite el RSS de la RSN en el CSP y pone el recuadro en el encabezado", () => {
  const html = readFileSync(path.join(here, "../../index.html"), "utf8");
  assert.match(html, /connect-src 'self' https:\/\/site\.api\.espn\.com https:\/\/rsn\.ucr\.ac\.cr;/);
  assert.match(html, /id="sis"/);
  assert.ok(html.indexOf('id="sis"') < html.indexOf('id="fx"'));
  assert.doesNotMatch(html, /cdn\.|unpkg|jsdelivr|cloudflare/i);
});

test("app.js pide el RSS de la RSN cada 5 min y usa setHref en los informes", () => {
  assert.match(appJs, /SIS_REFRESH_MS = 5 \* 60 \* 1000/);
  assert.match(appJs, /sisParseRss/);
  assert.match(appJs, /sisStartRefresh/);
  assert.match(appJs, /setHref\(a, href\)/);
  const code = appJs.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(code, /Notification|serviceWorker|pushManager/);
});

