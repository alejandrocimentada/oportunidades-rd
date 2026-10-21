// Tablero de Oportunidades RD. Sin dependencias externas.
// Todo el texto viene de páginas de terceros o de la investigación: siempre se escapa antes de mostrarlo.
"use strict";

const ESTADOS = window.ESTADOS;
const CLASE_ESTADO = {
  "Descubierta": "nuevo", "Me interesa": "interesa", "Investigando": "investigando", "Contacté": "contacte",
  "Aplicado": "aplicado", "Entrevista": "entrevista", "Oferta": "oferta", "Descartada": "descartado",
};
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "#");
const fecha = (iso) => (iso ? new Date(iso).toLocaleDateString("es-DO", { day: "numeric", month: "short" }) : "");
const pill = (estado) => `<span class="pill" style="background:var(--s-${CLASE_ESTADO[estado] || "nuevo"})">${esc(estado)}</span>`;
const enlace = (url, texto) => (url ? `<a href="${safeUrl(url)}" target="_blank" rel="noopener">${esc(texto)} ↗</a>` : "");
// «hay vacantes» en verde, «no hay» en gris, y lo que no se pudo revisar en ámbar.
const vacantesBadge = (e) => {
  const cls = e.vacantes === "hay vacantes" ? "hi" : e.vacantes === "no hay" ? "" : "mid";
  const txt = e.vacantes === "hay vacantes" ? `${e.vacantes_activas} ${e.vacantes_activas === 1 ? "vacante" : "vacantes"}` : e.vacantes;
  return `<span class="fit ${cls}" title="Vacantes abiertas en su página de empleos">${esc(txt)}</span>`;
};
const ICONO_OK = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>';

let state = { empresas: [], vacantes: [], resumen: null, abierta: null };

// Demo pública (GitHub Pages, scripts/construir_demo.py): no hay servidor. Las lecturas salen de
// window.DEMO (datos inventados) y nada se guarda.
// La demo se construyó el día `desde`: todas sus fechas (AAAA-MM-DD… y DD/MM/AAAA en las cartas) se mueven
// los días que hayan pasado, para que los seguimientos y el historial siempre se vean recientes.
function fechasDesdeHoy(datos, desde) {
  if (!datos || !desde) return datos;
  const [a, m, d] = desde.split("-").map(Number);
  const h = new Date();
  const dias = Math.round((Date.UTC(h.getFullYear(), h.getMonth(), h.getDate()) - Date.UTC(a, m - 1, d)) / 864e5);
  if (!dias) return datos;
  const mover = (a, m, d) => new Date(Date.UTC(+a, m - 1, +d + dias));
  const dos = (n) => String(n).padStart(2, "0");
  const cambiar = (v) => {
    if (typeof v === "string") {
      return v.replace(/^(\d{4})-(\d{2})-(\d{2})(?=(T[\d:.]+)?$)/, (_, a, m, d) => mover(a, m, d).toISOString().slice(0, 10))
        .replace(/\b(\d{2})\/(\d{2})\/(\d{4})\b/g, (_, d, m, a) => {
          const t = mover(a, m, d);
          return `${dos(t.getUTCDate())}/${dos(t.getUTCMonth() + 1)}/${t.getUTCFullYear()}`;
        });
    }
    if (Array.isArray(v)) return v.map(cambiar);
    if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, cambiar(x)]));
    return v;
  };
  return cambiar(datos);
}
const DEMO = fechasDesdeHoy(window.DEMO, window.DEMO_FECHA);
const AVISO_DEMO = "Es una demo: no se guarda nada. Instala el skill para usarlo con tu perfil.";

async function api(path, body) {
  if (DEMO) {
    if (body !== undefined || !(path in DEMO)) throw new Error(AVISO_DEMO);
    return JSON.parse(JSON.stringify(DEMO[path]));
  }
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.innerHTML = `${ICONO_OK}<span>${esc(msg)}</span>`;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), Math.max(2200, msg.length * 50));  // los avisos largos duran más
}

// -- página: reloj de la barra de menú y secciones que aparecen al bajar ------------------
const reloj = $("#reloj");
function tic() {
  if (!reloj) return;
  const d = new Date();
  const dia = d.toLocaleDateString("es-DO", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "");
  reloj.textContent = `${dia.charAt(0).toUpperCase()}${dia.slice(1)}  ${d.toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" })}`;
}
tic(); setInterval(tic, 30000);

// Al bajar, el escritorio pasa de tarjeta a ocupar toda la ventana, y la barra superior sube y se va (style.css,
// «.con-efecto»). --p: 1 arriba del todo (tarjeta), 0 tras bajar media pantalla. Sin efecto con movimiento reducido
// o en el teléfono.
const raiz = document.documentElement, barra = $(".top"), envoltura = $(".stage-wrap");
const quieto = matchMedia("(prefers-reduced-motion: reduce)"), estrecho = matchMedia("(max-width: 640px)");
let pendiente = false;
const conEfecto = () => !quieto.matches && !estrecho.matches;
function medirEscritorio() {
  raiz.classList.toggle("con-efecto", conEfecto());
  raiz.style.setProperty("--top", `${barra ? barra.offsetHeight : 0}px`);
  efectoEscritorio();
}
function efectoEscritorio() {
  pendiente = false;
  const avance = conEfecto() ? Math.min(1, Math.max(0, scrollY / (innerHeight * 0.5))) : 1;
  const p = conEfecto() ? 1 - avance : 1;
  const lado = Math.max(24, (raiz.clientWidth - 1152) / 2);
  raiz.style.setProperty("--p", p.toFixed(3));
  raiz.style.setProperty("--ix", `${(p * lado).toFixed(1)}px`);
  raiz.style.setProperty("--iy", `${(p * (barra ? barra.offsetHeight : 0)).toFixed(1)}px`);
  raiz.classList.toggle("moviendo", avance < 1);
  // La barra superior sigue al escritorio y, cuando el escritorio ya se fue de la pantalla, vuelve a bajar.
  const altoBarra = barra ? barra.offsetHeight : 0;
  const pasado = envoltura && scrollY > envoltura.offsetTop + envoltura.offsetHeight - altoBarra;
  const n = conEfecto() ? (pasado ? 1 : p) : 1;
  raiz.style.setProperty("--n", n.toFixed(3));
  raiz.classList.toggle("barra-fuera", n < 0.5);
}
addEventListener("scroll", () => { if (!pendiente) { pendiente = true; requestAnimationFrame(efectoEscritorio); } }, { passive: true });
addEventListener("resize", medirEscritorio);
quieto.addEventListener?.("change", medirEscritorio); estrecho.addEventListener?.("change", medirEscritorio);
medirEscritorio();
// Ir a la app desde un botón: con el efecto, arriba del todo (la tarjeta con la app); si no, hasta la ventana.
function irALaApp() {
  if (raiz.classList.contains("con-efecto") && envoltura) scrollTo({ top: envoltura.offsetTop, behavior: "smooth" });
  else $("#app").scrollIntoView({ behavior: "smooth", block: "start" });
}
if ("IntersectionObserver" in window) {
  const ver = new IntersectionObserver((xs) => xs.forEach((x) => { if (x.isIntersecting) { x.target.classList.add("in"); ver.unobserve(x.target); } }),
    { rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".reveal").forEach((el, i) => { el.style.transitionDelay = `${(i % 3) * 60}ms`; ver.observe(el); });
} else document.querySelectorAll(".reveal").forEach((el) => el.classList.add("in"));

// -- navegación -----------------------------------------------------------------------
function mostrar(view) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("on", v.id === `view-${view}`));
  try { localStorage.setItem("vista", view); } catch (_) { /* sin almacenamiento */ }
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => mostrar(b.dataset.view)));
// «Llenar mi perfil» y otros botones con data-ir: abre esa vista y sube a la ventana de la app.
document.querySelectorAll("[data-ir]").forEach((b) => b.addEventListener("click", () => {
  mostrar(b.dataset.ir);
  irALaApp();
}));

// -- resumen --------------------------------------------------------------------------
function pintarResumen() {
  const { resumen: r, novedades: nov, perfil_existe } = state.resumen;
  $("#aviso-perfil").hidden = perfil_existe;
  $("#aviso-empresas").hidden = !perfil_existe || r.total_empresas > 0;
  const pe = r.por_estado;
  const tiles = [
    ["Empresas", r.total_empresas, `${r.empresas_con_vacantes} con vacantes abiertas`],
    ["Me interesa", pe["Me interesa"] + pe["Investigando"], `${pe["Investigando"]} investigando`],
    ["Contactadas esta semana", r.contactadas_semana, "contacto o postulación", "accent"],
    ["Entrevistas", pe["Entrevista"], `${pe["Oferta"]} ofertas`, "green"],
    ["Seguimientos", r.seguimientos.length, "próximos 7 días"],
  ];
  $("#tiles").innerHTML = tiles.map(([k, v, s, tono]) =>
    `<div class="tile ${tono || ""}"><span>${esc(k)}</span><b>${v}</b><span>${esc(s)}</span></div>`).join("");
  $("#pipeline").innerHTML = ESTADOS.map((e) =>
    `<div data-estado="${esc(e)}" style="background:var(--s-${CLASE_ESTADO[e]})"><b>${pe[e]}</b>${esc(e)}</div>`).join("");
  document.querySelectorAll("#pipeline div").forEach((d) => d.addEventListener("click", () => {
    $("#f-estado").value = d.dataset.estado; pintarEmpresas(); mostrar("empresas");
  }));

  $("#recientes").innerHTML = r.recientes.map((e) => `<li data-id="${e.id}"><div class="grow">${esc(e.nombre)}
      <div class="sub">${esc(e.tipo)} · ${esc(e.presencia_rd || e.industria)}</div></div>${pill(e.estado)}</li>`).join("")
    || `<li class="empty">Todavía no hay empresas: pídele a tu agente «Busca empresas en RD para mi perfil».</li>`;
  $("#nov-fecha").textContent = nov.corrida ? `· revisión del ${new Date(nov.corrida.inicio).toLocaleString("es-DO")}` : "";
  const items = nov.nuevas.map((v) => `<li data-empresa="${v.empresa_id || ""}"><div class="grow">${esc(v.titulo)}
      <div class="sub">${esc(v.empresa_nombre)} · ${esc(v.ubicacion || "sin ubicación")}</div></div><span class="tag">nueva</span></li>`);
  items.push(...nov.ya_no_aparecen.map((v) => `<li data-empresa="${v.empresa_id || ""}"><span class="tag">ya no aparece</span>
      <div class="grow">${esc(v.titulo)}<div class="sub">${esc(v.empresa_nombre)}</div></div></li>`));
  $("#novedades").innerHTML = items.join("") || `<li class="empty">${nov.corrida ? "Nada nuevo desde la revisión anterior." : "Todavía no se han revisado las páginas de empleo."}</li>`;

  $("#seguimientos").innerHTML = r.seguimientos.map((e) => `<li data-id="${e.id}"><div class="grow">${esc(e.nombre)}
      <div class="sub">${esc(e.estado)}</div></div>
      <span class="${e.vencido ? "overdue" : "sub"}">${e.vencido ? "vencido " : ""}${fecha(e.seguimiento + "T12:00")}</span></li>`).join("")
    || `<li class="empty">Nada pendiente.</li>`;
  $("#manuales").innerHTML = (nov.manuales || []).map((m) => `<li class="static"><b>${esc(m.empresa)}</b>
      <span class="tag">${esc(m.estado)}</span><div class="sub">${esc(m.motivo)}</div>
      <a href="${safeUrl(m.enlace)}" target="_blank" rel="noopener">Abrir página de empleos ↗</a></li>`).join("")
    || `<li class="empty">Nada que revisar a mano.</li>`;
  document.querySelectorAll("#recientes li[data-id], #seguimientos li[data-id]").forEach((li) =>
    li.addEventListener("click", () => abrir(+li.dataset.id)));
  document.querySelectorAll("#novedades li[data-empresa]").forEach((li) =>
    li.addEventListener("click", () => { if (li.dataset.empresa) abrir(+li.dataset.empresa); }));
}

// -- tablero (kanban de empresas) -----------------------------------------------------
function pintarTablero() {
  $("#board").innerHTML = ESTADOS.map((s) => {
    const es = state.empresas.filter((e) => e.estado === s);
    return `<div class="col" data-estado="${esc(s)}"><h3><span style="--dot:var(--s-${CLASE_ESTADO[s]})">${esc(s)}</span><i>${es.length}</i></h3>
      ${es.map((e) => `<div class="kcard" draggable="true" data-id="${e.id}">
        <div class="t">${esc(e.nombre)}</div>
        <div class="c">${esc(e.tipo)} · ${esc(e.industria)}</div>
        ${e.equipos.length ? `<div class="c">${esc(e.equipos[0])}</div>` : ""}
        <div class="m">${vacantesBadge(e)}${e.alertas.length ? `<span class="warn" title="${esc(e.alertas.join(" · "))}">⚠ ${e.alertas.length} ${e.alertas.length === 1 ? "alerta" : "alertas"}</span>` : ""}</div>
      </div>`).join("")}</div>`;
  }).join("");
  document.querySelectorAll(".kcard").forEach((c) => {
    c.addEventListener("click", () => abrir(+c.dataset.id));
    c.addEventListener("dragstart", (ev) => { ev.dataTransfer.setData("text/plain", c.dataset.id); c.classList.add("dragging"); });
    c.addEventListener("dragend", () => c.classList.remove("dragging"));
  });
  document.querySelectorAll(".col").forEach((col) => {
    col.addEventListener("dragover", (ev) => { ev.preventDefault(); col.classList.add("over"); });
    col.addEventListener("dragleave", () => col.classList.remove("over"));
    col.addEventListener("drop", async (ev) => {
      ev.preventDefault(); col.classList.remove("over");
      await cambiarEstado(+ev.dataTransfer.getData("text/plain"), col.dataset.estado);
    });
  });
}

async function cambiarEstado(id, estado) {
  const e = state.empresas.find((x) => x.id === id);
  if (!e || e.estado === estado) return;
  try {
    await api(`/api/empresas/${id}/estado`, { estado });
    toast(`«${e.nombre}» → ${estado}`);
    await cargar();
    if (state.abierta === id) abrir(id);
  } catch (err) {
    toast(err.message);
    if (state.abierta === id) $("#d-estado").value = e.estado;  // no se guardó: el selector vuelve al estado real
  }
}

// -- empresas -------------------------------------------------------------------------
function pintarEmpresas() {
  const texto = $("#f-texto").value.toLowerCase();
  const est = $("#f-estado").value, tipo = $("#f-tipo").value, ind = $("#f-industria").value;
  const conVac = $("#f-con-vacantes").checked;
  const es = state.empresas.filter((e) => (!est || e.estado === est) && (!tipo || e.tipo === tipo)
    && (!ind || e.industria === ind) && (!conVac || e.vacantes_activas > 0)
    && (!texto || [e.nombre, ...e.equipos, ...e.roles.map((r) => r.rol)].join(" ").toLowerCase().includes(texto)));
  $("#companies").innerHTML = es.map((e) => `<article class="company" data-id="${e.id}" tabindex="0">
      <header><div class="c-logo" aria-hidden="true">${esc((e.nombre || "?").trim().charAt(0).toUpperCase())}</div>
        <div class="grow"><h3>${esc(e.nombre)}</h3><span class="sub">${esc(e.tipo)} · ${esc(e.industria)}</span></div>
        ${vacantesBadge(e)}</header>
      <p class="why">${esc(e.presencia_rd)}</p>
      ${e.equipos.length ? `<div class="roles">${e.equipos.map((t) => `<span class="chip-s">${esc(t)}</span>`).join("")}</div>` : ""}
      ${e.roles.length ? `<div class="sub">Roles probables: ${e.roles.slice(0, 3).map((r) => esc(r.rol)).join(" · ")}</div>` : ""}
      <div class="foot">${pill(e.estado)}
        ${e.fuentes_presencia[0] ? enlace(e.fuentes_presencia[0].url, "Fuente de presencia en RD") : ""}
        ${enlace(e.sitio_web, "Sitio web")}
        ${e.alertas.length ? `<span class="tag" title="${esc(e.alertas.join(" · "))}">⚠ ${e.alertas.length}</span>` : ""}
      </div>
    </article>`).join("") || `<p class="hint">${state.empresas.length ? "Ninguna empresa con estos filtros." : "Todavía no hay empresas. Pídele a tu agente: «Busca empresas en RD para mi perfil»."}</p>`;
  document.querySelectorAll(".company[data-id]").forEach((c) => {
    c.addEventListener("click", (ev) => { if (!ev.target.closest("a")) abrir(+c.dataset.id); });
    c.addEventListener("keydown", (ev) => { if (ev.key === "Enter") abrir(+c.dataset.id); });
  });
}
["#f-texto", "#f-estado", "#f-tipo", "#f-industria", "#f-con-vacantes"].forEach((s) => $(s).addEventListener("input", pintarEmpresas));

// -- vacantes (comprobación secundaria) -----------------------------------------------
function pintarVacantes() {
  const texto = $("#v-texto").value.toLowerCase();
  const emp = $("#v-empresa").value;
  const solo = $("#v-activas").checked;
  const vs = state.vacantes.filter((v) => (!emp || v.empresa_nombre === emp) && (!solo || v.activa)
    && (!texto || `${v.titulo} ${v.empresa_nombre}`.toLowerCase().includes(texto)));
  $("#tbl-vacantes tbody").innerHTML = vs.map((v) => `<tr data-empresa="${v.empresa_id || ""}" class="${v.activa ? "" : "inactive"}">
      <td><b>${esc(v.titulo)}</b><span class="sub">${esc(v.empresa_nombre || "—")} · ${esc(v.ubicacion || "sin ubicación")}</span>
        ${v.fuente === "pegado" ? ' <span class="tag">pegada</span>' : ""}${v.activa ? "" : ' <span class="tag">ya no aparece</span>'}</td>
      <td>${fecha(v.primera_vez)}</td>
      <td>${v.url ? `<a class="btn small" href="${safeUrl(v.url)}" target="_blank" rel="noopener">Ver anuncio</a>` : ""}</td></tr>`).join("")
    || `<tr><td colspan="3" class="hint">${state.vacantes.length ? "No hay vacantes con estos filtros." : "Todavía no se han revisado las páginas de empleo de tus empresas."}</td></tr>`;
  document.querySelectorAll("#tbl-vacantes tbody tr[data-empresa]").forEach((tr) => tr.addEventListener("click", (ev) => {
    if (!ev.target.closest("a") && tr.dataset.empresa) abrir(+tr.dataset.empresa);
  }));
}
["#v-texto", "#v-empresa", "#v-activas"].forEach((s) => $(s).addEventListener("input", pintarVacantes));

// -- detalle de una empresa -----------------------------------------------------------
async function abrir(id) {
  const e = await api(`/api/empresas/${id}`);
  state.abierta = id;
  const puedeDocs = state.resumen.con_documentos.includes(e.estado);
  const lista = (xs, cls, vacio) => xs.length ? `<div class="box ${cls}"><ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`
    : `<div class="box none">${vacio}</div>`;
  const enlaces = (xs, clave, vacio) => xs.length ? `<ul class="links">${xs.map((x) =>
    `<li>${x.url ? `<a href="${safeUrl(x.url)}" target="_blank" rel="noopener">${esc(x[clave] || x.url)} ↗</a>` : esc(x[clave])}</li>`).join("")}</ul>`
    : `<div class="box none">${vacio}</div>`;
  const doc = (tipo, titulo, texto) => `<div class="doc"><header>${titulo}
      <span><button class="btn small ghost" data-gen="${tipo}" ${puedeDocs ? "" : "disabled"}>${texto ? "Rehacer" : "Preparar"}</button>
      ${texto ? `<button class="btn small" data-copy="${tipo}"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h9"/></svg>Copiar</button>` : ""}</span></header>
      ${texto ? `<textarea id="doc-${tipo}" rows="${tipo === "carta" ? 12 : 6}" readonly>${esc(texto)}</textarea>` : ""}</div>`;
  const postular = [[e.url_empleos, "Página de empleos"], [e.portal_rd, "Portal filtrado a RD"],
    [e.talento, "Banco de talento / postulación general"], [e.linkedin, e.linkedin_empresa ? "LinkedIn de la empresa" : "Buscar la empresa en LinkedIn"]]
    .filter(([u]) => u).map(([u, t]) => `<li>${enlace(u, t)}</li>`).join("");
  const nivel = e.vacantes === "hay vacantes" ? "hi" : e.vacantes === "no hay" ? "none" : "mid";
  $("#drawer-body").innerHTML = `
    <div class="d-head"><h2>${esc(e.nombre)}</h2><div class="sub">${esc(e.tipo)} · ${esc(e.industria)}</div>
      ${e.sitio_web ? `<div class="sub">${enlace(e.sitio_web, "Sitio web")}</div>` : ""}</div>
    <div class="d-body">
    <div class="d-fit ${nivel}"><div><h3>Vacantes abiertas · ${esc(e.vacantes)}</h3>
      <div class="sub">${esc(e.nota_rastreo || ({ pendiente: "Todavía no se ha revisado su página de empleos.", "sin página": "No tiene página de empleos guardada." }[e.estado_rastreo] || ""))}${e.ultimo_rastreo ? ` · revisada ${fecha(e.ultimo_rastreo)}` : ""}</div></div>
      <b>${e.vacantes_activas}</b></div>
    ${e.lista_vacantes.filter((v) => v.activa).length ? `<ul class="links mt-s">${e.lista_vacantes.filter((v) => v.activa).map((v) =>
      `<li>${v.url ? `<a href="${safeUrl(v.url)}" target="_blank" rel="noopener">${esc(v.titulo)} ↗</a>` : esc(v.titulo)}${v.ubicacion ? ` <span class="sub">· ${esc(v.ubicacion)}</span>` : ""}</li>`).join("")}</ul>` : ""}
    <div class="d-sec"><h3>Presencia en RD</h3><p class="p">${esc(e.presencia_rd || "—")}</p>${enlaces(e.fuentes_presencia, "titulo", "Sin fuentes.")}</div>
    <div class="d-sec"><h3>Equipos que encajan contigo</h3>${e.equipos.length ? `<div class="roles">${e.equipos.map((t) => `<span class="chip-s">${esc(t)}</span>`).join("")}</div>` : '<div class="box none">—</div>'}</div>
    <div class="d-sec"><h3>Roles probables</h3>${e.roles.length ? `<ul class="rolelist">${e.roles.map((r) =>
      `<li><b>${esc(r.rol)}</b>${r.razon ? `<span>${esc(r.razon)}</span>` : ""}</li>`).join("")}</ul>` : '<div class="box none">—</div>'}</div>
    <div class="d-sec"><h3>Evidencia en RD</h3>${enlaces(e.evidencia, "texto", "Sin evidencia de equipos o vacantes pasadas todavía.")}</div>
    <div class="d-sec"><h3>Por qué encaja</h3>${lista(e.razones, "good", "—")}</div>
    <div class="d-sec"><h3>Señales de alerta</h3>${lista(e.alertas, "warn", "Ninguna detectada.")}</div>
    <div class="d-sec"><h3>Cómo postular</h3>${postular ? `<ul class="links">${postular}</ul>` : '<div class="box none">—</div>'}</div>
    <div class="d-sec"><h3>A quién contactar (roles)</h3><div class="roles">
      ${e.contactos.map((c) => `<a href="${safeUrl(c.linkedin)}" target="_blank" rel="noopener" title="Buscar en LinkedIn">${esc(c.rol)} ↗</a>`).join("")}</div></div>
    <div class="d-sec"><h3>Mensaje y carta</h3>
      ${puedeDocs ? "" : '<p class="hint">Marca la empresa «Me interesa» para preparar el mensaje y la carta.</p>'}
      ${puedeDocs && e.roles.length > 1 ? `<label class="d-rol">Centrar en el rol <select id="d-rol">${e.roles.map((r) => `<option>${esc(r.rol)}</option>`).join("")}</select></label>` : ""}
      ${doc("mensaje", "Mensaje corto (LinkedIn / correo)", e.mensaje)}
      ${doc("carta", "Carta de postulación general", e.carta)}
      <p class="hint" style="margin-top:6px">Se guardan como archivos en <code>data/documentos</code>. Nada se envía solo.</p></div>
    <div class="d-sec"><h3>Notas</h3><textarea id="d-nota" rows="3" placeholder="Escribe aquí; se guarda solo">${esc(e.nota)}</textarea></div>
    <div class="d-sec"><h3>Historial</h3><ul class="timeline">${e.historial.map((h) => `<li>${esc(h.a_estado)}
      <div class="sub">${new Date(h.fecha).toLocaleString("es-DO")}${h.nota ? " · " + esc(h.nota) : ""}</div></li>`).join("")}</ul></div>
    </div>
    <div class="d-actions"><label>Mover a <select id="d-estado">${ESTADOS.map((s) => `<option ${s === e.estado ? "selected" : ""}>${esc(s)}</option>`).join("")}</select></label>
      <label>Seguimiento <input type="date" id="d-seg" value="${esc(e.seguimiento)}"></label></div>`;
  $("#d-estado").addEventListener("change", (ev) => cambiarEstado(id, ev.target.value));
  $("#d-seg").addEventListener("change", async (ev) => {
    try { await api(`/api/empresas/${id}/seguimiento`, { fecha: ev.target.value }); toast("Seguimiento guardado"); cargar(); } catch (err) { toast(err.message); }
  });
  $("#d-nota").addEventListener("change", async (ev) => {
    try { await api(`/api/empresas/${id}/nota`, { nota: ev.target.value }); toast("Nota guardada"); } catch (err) { toast(err.message); }
  });
  document.querySelectorAll("[data-gen]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true; b.textContent = "Preparando…";
    try {
      const r = await api(`/api/empresas/${id}/generar`, { tipo: b.dataset.gen, rol: $("#d-rol") ? $("#d-rol").value : "" });
      toast(`Listo (${r.origen})`); abrir(id);
    } catch (err) { toast(err.message); b.disabled = false; b.textContent = "Preparar"; }
  }));
  document.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    const texto = $(`#doc-${b.dataset.copy}`).value;
    try { await navigator.clipboard.writeText(texto); } catch (_) { $(`#doc-${b.dataset.copy}`).select(); document.execCommand("copy"); }
    toast("Copiado");
  }));
  $("#drawer").classList.add("open"); $("#scrim").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
}
function cerrar() {
  state.abierta = null;
  $("#drawer").classList.remove("open"); $("#scrim").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
}
$("#drawer-close").addEventListener("click", cerrar);
$("#scrim").addEventListener("click", cerrar);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });

// -- mi perfil (encuesta, una pregunta a la vez) y revisión de vacantes ---------------------------------------
const LISTAS = ["roles_objetivo", "habilidades", "idiomas"];
const leer = (obj, ruta) => ruta.split(".").reduce((o, k) => (o ?? {})[k], obj);
let sugerenciasAgente = {};  // las que el agente refinó (perfil.sugerencias); van primero
let ESCO = null;  // índice local de ESCO (static/esco.json), preparado al abrir la pregunta de habilidades

function llenarPerfil(perfil) {
  const f = $("#form-perfil");
  f.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name || el.name.startsWith("_")) return;
    if (el.name === "intereses") { el.checked = (perfil.intereses || []).includes(el.value); return; }
    let v = leer(perfil, el.name);
    if (el.name === "tiene_experiencia") v = v === true ? "si" : v === false ? "no" : "";
    if (["edad", "preferencias.salario_minimo_dop"].includes(el.name) && !v) v = "";  // 0 = sin responder
    if (el.type === "radio") el.checked = el.value === v;
    else if (el.type === "checkbox") el.checked = !!v;
    else if (LISTAS.includes(el.name)) el.value = (v || []).join("\n");
    else el.value = v ?? "";
  });
  $("#interes-otra").checked = !!perfil.intereses_otra;
  $("#otra-lbl").hidden = !perfil.intereses_otra;
  sugerenciasAgente = perfil.sugerencias || {};
  document.querySelectorAll(".chipbox").forEach(pintarChips);
}

// Chips: la lista vive en el <textarea hidden> del mismo campo (una por línea), que es lo que se guarda.
const chipCampo = (box) => $(`#form-perfil textarea[name="${box.dataset.for}"]`);
const chipValores = (box) => chipCampo(box).value.split("\n").map((x) => x.trim()).filter(Boolean);
function pintarChips(box) {
  const vals = chipValores(box);
  box.querySelector(".list-chips").innerHTML = vals.map((x, i) =>
    `<span class="chip">${esc(x)}<button type="button" data-quitar="${i}" aria-label="Quitar ${esc(x)}">×</button></span>`).join("")
    || `<span class="vacio">Todavía no hay ninguno.</span>`;
  pintarSugerencias();
}
function agregarChips(box, texto) {
  const nuevos = texto.split(/[;\n]/).map((x) => x.trim()).filter(Boolean);
  if (!nuevos.length) return;
  const vals = chipValores(box);
  nuevos.forEach((x) => { if (!vals.some((v) => v.toLowerCase() === x.toLowerCase())) vals.push(x); });
  chipCampo(box).value = vals.join("\n");
  pintarChips(box);
}
document.querySelectorAll(".chipbox").forEach((box) => {
  const conCampo = !box.classList.contains("solo-lista");  // idiomas: se añaden con su propio selector
  box.innerHTML = (conCampo ? `<div class="add"><input class="campo" id="chip-${box.dataset.for}" placeholder="${esc(box.dataset.placeholder)}">
    <button type="button" class="btn">Añadir</button></div>` : "") + `<div class="list-chips"></div>`;
  const input = box.querySelector("input");
  const agregar = () => { agregarChips(box, input.value); input.value = ""; input.focus(); };
  if (conCampo) box.querySelector(".add button").addEventListener("click", agregar);
  input?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { if (input.value.trim()) { ev.preventDefault(); agregar(); } }  // vacío: Enter = OK
    else if (ev.key === "Backspace" && !input.value) {  // borrar el último chip con el campo vacío
      const vals = chipValores(box); vals.pop(); chipCampo(box).value = vals.join("\n"); pintarChips(box);
    }
  });
  box.querySelector(".list-chips").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-quitar]");
    if (!b) return;
    const vals = chipValores(box); vals.splice(+b.dataset.quitar, 1);
    chipCampo(box).value = vals.join("\n"); pintarChips(box);
  });
  pintarChips(box);
});

// -- buscador de habilidades: índice local (ESCO + habilidades curadas), funciona sin conexión ----
// Se carga una sola vez, al abrir habilidades o roles; mientras tanto el campo acepta texto libre.
function cargarEsco() {
  cargarEsco.p ??= fetch(window.RUTA_ESCO).then((r) => (r.ok ? r.json() : null))
    .then((d) => { if (d) { ESCO = Sugerencias.prepararEsco(d); pintarSugerencias(); acPintar(); } })
    .catch(() => { /* sin índice: quedan las sugerencias del mapa y el texto libre */ });
  return cargarEsco.p;
}
const acInput = $("#chip-habilidades"), acBox = acInput.closest(".chipbox");
const acLista = Object.assign(document.createElement("ul"), { id: "ac-habilidades", className: "ac", hidden: true });
acLista.setAttribute("role", "listbox");
acLista.setAttribute("aria-label", "Habilidades que coinciden");
acInput.parentElement.append(acLista);
Object.entries({ role: "combobox", "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": acLista.id,
  autocomplete: "off" }).forEach(([k, v]) => acInput.setAttribute(k, v));
let acItems = [], acSel = -1;

// Resalta las palabras buscadas, sin importar tildes: «diseno» marca «Diseño».
function resaltar(texto, consulta) {
  const plano = [...texto].map((c) => c.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().charAt(0) || " ").join("");
  const marcas = new Array(texto.length).fill(false);
  for (const p of Sugerencias.normalizar(consulta).split(" ").filter(Boolean)) {
    const m = new RegExp(`(^|[^a-z0-9])(${p.replace(/[^a-z0-9]/g, "")})`).exec(plano);
    if (m) for (let k = m.index + m[1].length; k < m.index + m[0].length; k++) marcas[k] = true;
  }
  return [...texto].map((c, k) => (marcas[k] && !marcas[k - 1] ? "<mark>" : "") + esc(c)
    + (marcas[k] && !marcas[k + 1] ? "</mark>" : "")).join("");
}
function acCerrar() {
  acLista.hidden = true; acSel = -1;
  acInput.setAttribute("aria-expanded", "false"); acInput.removeAttribute("aria-activedescendant");
}
function acPintar() {
  const q = acInput.value.trim();
  if (!q || document.activeElement !== acInput) { acCerrar(); return; }
  acItems = Sugerencias.buscarHabilidades(q, ESCO);
  acSel = Math.min(acSel, acItems.length);
  // El nombre en español y, debajo y en pequeño, el inglés solo si es distinto (y el sinónimo que coincidió).
  const opciones = acItems.map((r, i) => {
    const debajo = [Sugerencias.normalizar(r.en) !== Sugerencias.normalizar(r.es) ? resaltar(r.en, q) : "",
      r.sinonimo ? `también «${resaltar(r.sinonimo, q)}»` : ""].filter(Boolean).join(" · ");
    return `<li role="option" id="ac-op-${i}" data-i="${i}"><b>${resaltar(mayus(r.es), q)}</b>${debajo ? `<small>${debajo}</small>` : ""}</li>`;
  });
  if (!ESCO) opciones.push('<li class="ac-nota" aria-disabled="true">Cargando el buscador de habilidades…</li>');
  else if (q.length >= 2 && !acItems.length) opciones.push('<li class="ac-nota" aria-disabled="true">No está en la lista: puedes añadirla igual.</li>');
  opciones.push(`<li role="option" id="ac-op-${acItems.length}" data-i="${acItems.length}" class="ac-libre">Añadir «${esc(q)}» tal cual</li>`);
  acLista.innerHTML = opciones.join("");
  acLista.hidden = false;
  // La ventana de la app recorta lo que se sale (esquinas redondeadas): la lista cabe en el espacio de abajo.
  const abajo = $("#app").getBoundingClientRect().bottom - acInput.getBoundingClientRect().bottom - 12;
  acLista.style.maxHeight = `${Math.max(160, Math.min(340, abajo))}px`;
  acInput.setAttribute("aria-expanded", "true");
  acMarcar();
}
function acMarcar() {
  acLista.querySelectorAll("[role=option]").forEach((li) => li.setAttribute("aria-selected", String(+li.dataset.i === acSel)));
  if (acSel >= 0) { acInput.setAttribute("aria-activedescendant", `ac-op-${acSel}`); $(`#ac-op-${acSel}`).scrollIntoView({ block: "nearest" }); }
  else acInput.removeAttribute("aria-activedescendant");
}
function acElegir(i) {
  agregarChips(acBox, i < acItems.length ? mayus(acItems[i].es) : acInput.value);
  acInput.value = "";
  acCerrar();
  acInput.focus();
}
const mayus = (t) => t.charAt(0).toUpperCase() + t.slice(1);
acInput.addEventListener("input", () => { cargarEsco(); acSel = -1; acPintar(); });
acInput.addEventListener("focus", cargarEsco);
acInput.addEventListener("blur", () => setTimeout(acCerrar, 120));
// En fase de captura, antes que el Enter del chipbox: Enter con una opción marcada la añade; sin marcar, texto libre.
acInput.addEventListener("keydown", (ev) => {
  if (acLista.hidden) return;
  const total = acItems.length + 1;
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    ev.preventDefault();
    acSel = ev.key === "ArrowDown" ? (acSel + 1) % total : (acSel <= 0 ? total - 1 : acSel - 1);
    acMarcar();
  } else if (ev.key === "Enter" && acSel >= 0) {
    ev.preventDefault(); ev.stopImmediatePropagation(); acElegir(acSel);
  } else if (ev.key === "Escape") {
    ev.preventDefault(); ev.stopImmediatePropagation(); acCerrar();
  } else if (ev.key === "Enter" || ev.key === "Tab") acCerrar();
}, true);
acLista.addEventListener("mousedown", (ev) => {  // mousedown: antes de que el campo pierda el foco
  const li = ev.target.closest("[role=option]");
  if (li) { ev.preventDefault(); acElegir(+li.dataset.i); }
});

// Encuesta: una pregunta por pantalla (Enter = OK), con barra de progreso, flechas y un final con el resumen.
// Cada respuesta se guarda al pulsar OK; las obligatorias (data-req) muestran su aviso en vez de avanzar.
const PANTALLAS = [...document.querySelectorAll("#form-perfil .q")];
const FIN = PANTALLAS.length - 1;  // la última pantalla es «¡Listo!»
const MAC = /Mac|iP(hone|ad|od)/.test(navigator.platform);
const ICONO_CHECK = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.5 3.5 7.5-8"/></svg>';
let actual = -1, volverAlFinal = false, guardando = false;

PANTALLAS.slice(0, FIN).forEach((q, i) => {
  q.querySelector(".q-t").insertAdjacentHTML("afterbegin", `<span class="q-num">${i + 1}<span aria-hidden="true">→</span></span>`);
  q.querySelectorAll(".opcion").forEach((o, k) => {  // letras A, B, C… para elegir con el teclado
    o.dataset.letra = String.fromCharCode(65 + k);
    o.querySelector("input + span").insertAdjacentHTML("afterbegin", `<kbd class="letra" aria-hidden="true">${o.dataset.letra}</kbd>`);
  });
  const enter = q.querySelector("textarea:not([hidden])") ? `${MAC ? "⌘" : "Ctrl"} + Enter ↵` : "Enter ↵";
  q.insertAdjacentHTML("beforeend", `<p class="q-error" role="alert"></p><div class="q-acciones">
    <button type="button" class="q-ok" data-ok>OK ${ICONO_CHECK}</button>
    ${"opcional" in q.dataset ? '<button type="button" class="q-saltar" data-saltar>Saltar</button>' : ""}
    <span class="q-pista">pulsa <b>${enter}</b></span></div>`);
});
PANTALLAS[FIN].querySelector(".q-t").tabIndex = -1;

// Preguntas con data-si="tiene_experiencia" solo salen si la respuesta fue «Sí».
const tieneExperiencia = () => $("[name=tiene_experiencia]:checked")?.value === "si";
const visible = (q) => !q.dataset.si || tieneExperiencia();
const visibles = () => PANTALLAS.slice(0, FIN).filter(visible);
function vecina(i, paso) {  // la siguiente (o anterior) pregunta visible; al pasar la última, el final
  for (let j = i + paso; j >= 0 && j < FIN; j += paso) if (visible(PANTALLAS[j])) return j;
  return paso > 0 ? FIN : i;
}
function numerar() {
  visibles().forEach((q, k) => { q.querySelector(".q-num").firstChild.textContent = k + 1; });
  $("#inicio-n").textContent = visibles().length;
}
const enfocables = (q) => [...q.querySelectorAll("input, textarea:not([hidden]), select, button, summary, a[href]")]
  .filter((el) => el.offsetParent !== null && !el.disabled);
function enfocar(q) {
  // La primera respuesta (no las sugerencias); en el final, el título, para que se anuncie.
  const el = q === PANTALLAS[FIN] ? q.querySelector(".q-t") : enfocables(q).find((x) => !x.closest(".sug"));
  if (!el) return;
  el.focus({ preventScroll: !estrecho.matches });
  // En la ventana (que se desplaza por dentro), que la respuesta enfocada quede a la vista.
  const wb = $(".win-body"), abajo = el.getBoundingClientRect().bottom - wb.getBoundingClientRect().bottom + 24;
  if (!estrecho.matches && abajo > 0) wb.scrollTop += abajo;
}
function avisar(q, msg) { q.querySelector(".q-error").textContent = msg ? `⚠ ${msg}` : ""; }

function falta(q) {
  if (!("req" in q.dataset)) return "";
  const box = q.querySelector(".chipbox");
  let hay;
  const radios = q.querySelectorAll("input[type=radio]:not([name^=_])");
  if (box) {
    const i = box.querySelector("input");
    if (i) { agregarChips(box, i.value); i.value = ""; }
    hay = chipValores(box).length > 0 || !!q.querySelector("[name=roles_abiertos]:checked");
  } else if (radios.length && !q.querySelector("[required]")) hay = [...radios].some((r) => r.checked);
  else if (q.querySelector("[name=intereses]")) hay = perfilDelFormulario().intereses.length > 0 || !!$("[name=intereses_otra]").value.trim();
  else hay = [...q.querySelectorAll("[required]")].every((el) => el.value.trim());
  return hay ? "" : q.dataset.req;
}
function invalido(q) {
  const el = [...q.querySelectorAll("input")].find((x) => !x.checkValidity());
  if (!el) return "";
  if (el.type === "email") return "Escribe un correo válido, como nombre@ejemplo.com.";
  return el.type === "url" ? "Escribe el enlace completo, empezando con https://."
    : `Escribe un número${el.max ? ` entre ${el.min || 0} y ${el.max}` : " válido"}.`;
}

function irA(i, { foco = true, animar = true } = {}) {
  i = Math.max(0, Math.min(FIN, i));
  const viejo = PANTALLAS[actual], nuevo = PANTALLAS[i], atras = i < actual;
  const moverse = animar && viejo && viejo !== nuevo && !quieto.matches;
  actual = i;
  $("#view-perfil").classList.remove("en-inicio");
  if (i === FIN) { volverAlFinal = false; pintarFin(); }
  numerar();
  const vis = visibles(), pos = i === FIN ? vis.length : vis.indexOf(nuevo);
  $("#q-barra").style.width = `${(Math.max(0, pos) / vis.length) * 100}%`;
  $("#q-prev").disabled = i === 0 || vecina(i, -1) === i;
  $("#q-next").disabled = i === FIN;
  clearTimeout(irA.t);
  const mostrarNuevo = () => {
    PANTALLAS.forEach((p) => p.classList.remove("on", "sale", "entra", "atras"));
    nuevo.classList.add("on");
    if (moverse) nuevo.classList.add("entra", ...(atras ? ["atras"] : []));
    if (nuevo.querySelector(".sug")) cargarEsco();
    pintarSugerencias();
    if (!estrecho.matches) $(".win-body").scrollTop = 0;
    if (foco) enfocar(nuevo);
  };
  // La pregunta actual sube y se desvanece; la siguiente entra desde abajo (al volver, al revés).
  if (moverse && viejo.classList.contains("on")) {
    viejo.classList.add("sale"); viejo.classList.toggle("atras", atras);
    irA.t = setTimeout(mostrarNuevo, 140);
  } else mostrarNuevo();
}

async function ok() {
  const q = PANTALLAS[actual];
  if (actual >= FIN || guardando) return;
  const msg = falta(q) || invalido(q);
  avisar(q, msg);
  if (msg) { enfocar(q); return; }
  await avanzar(q, volverAlFinal ? FIN : vecina(actual, 1));
}
// Se guarda solo al llegar al final (con OK o con «Saltar»); en la demo, nunca.
async function avanzar(q, destino) {
  if (!DEMO && destino === FIN) {
    guardando = true;
    try { await guardarPerfil(); } catch (e) { avisar(q, e.message); return; } finally { guardando = false; }
    cargar().catch(() => { /* el resumen se actualiza en la próxima carga */ });
  }
  irA(destino);
}
function saltar() {
  if (actual >= FIN || guardando) return;
  const q = PANTALLAS[actual]; avisar(q, "");
  avanzar(q, volverAlFinal ? FIN : vecina(actual, 1));
}

// Pantalla final: cada respuesta en corto; un clic vuelve a esa pregunta y, con OK, de vuelta aquí.
function respuesta(q) {
  const partes = [];
  const unidad = (n, uno, varios) => `${n} ${n === "1" ? uno : varios}`;
  q.querySelectorAll("input[name], select[name], textarea[name]").forEach((el) => {
    if (el.closest(".avanzado") || el.name.startsWith("_")) return;
    if (el.type === "checkbox" || el.type === "radio") {
      if (el.checked) partes.push(el.dataset.resumen || el.closest("label").querySelector("b").textContent);
    } else if (LISTAS.includes(el.name)) partes.push(chipValores(q.querySelector(".chipbox")).join(", "));
    else if (el.value.trim() && !(el.name === "preferencias.dias_remotos" && +el.value === 0)) {
      partes.push({ anos_experiencia: unidad(el.value, "año", "años"), "preferencias.dias_remotos": unidad(el.value, "día remoto", "días remotos"),
        "preferencias.salario_minimo_dop": `RD$ ${Number(el.value).toLocaleString("es-DO")}` }[el.name] || el.value.trim());
    }
  });
  return partes.filter(Boolean).join(" · ");
}
function pintarFin() {
  $("#fin-resumen").innerHTML = visibles().map((q, k) => {
    const r = respuesta(q), i = PANTALLAS.indexOf(q);
    return `<button type="button" class="fin-item" data-editar="${i}" aria-label="Cambiar: ${esc(q.dataset.corto)}">
      <span>${k + 1}. ${esc(q.dataset.corto)}</span>${r ? `<b>${esc(r)}</b>` : '<b class="sin">Sin responder</b>'}</button>`;
  }).join("");
}

$("#form-perfil").addEventListener("click", (ev) => {
  if (ev.target.closest("[data-ok]")) ok();
  else if (ev.target.closest("[data-saltar]")) saltar();
  else if (ev.target.closest("[data-alternar]") && actual < FIN) avisar(PANTALLAS[actual], "");
  const ed = ev.target.closest("[data-editar]");
  if (ed) { volverAlFinal = true; irA(+ed.dataset.editar); }
});
$("#form-perfil").addEventListener("input", () => { if (actual < FIN) avisar(PANTALLAS[actual], ""); });
$("#form-perfil").addEventListener("change", (ev) => { if (ev.target.name === "tiene_experiencia") numerar(); });
$("#q-prev").addEventListener("click", () => irA(vecina(actual, -1)));
$("#q-next").addEventListener("click", ok);

// Teclado: Enter = OK (Ctrl/⌘ + Enter en textos largos), Shift+Tab desde la primera respuesta o ↑ = atrás,
// y la letra de una opción la marca. Los botones, listas y el buscador de habilidades conservan sus teclas.
const escribiendo = (el) => el.matches("textarea, select, input:not([type=checkbox]):not([type=radio])");
document.addEventListener("keydown", (ev) => {
  const t = ev.target;
  if (!$("#view-perfil").classList.contains("on") || ev.defaultPrevented || ev.isComposing) return;
  if (enInicio()) {  // portada: Enter empieza
    if (ev.key === "Enter" && (t === document.body || t.closest("#q-inicio"))) { ev.preventDefault(); empezar(); }
    return;
  }
  if (actual >= FIN) return;
  if (t !== document.body && !t.closest("#view-perfil")) return;
  const q = PANTALLAS[actual];
  if (ev.key === "Enter") {
    if (t.tagName === "TEXTAREA" ? !(ev.ctrlKey || ev.metaKey) : t.matches("button, summary, select, a")) return;
    ev.preventDefault(); ok();
  } else if (ev.key === "Tab" && ev.shiftKey && actual > 0 && t === enfocables(q)[0]) {
    ev.preventDefault(); irA(vecina(actual, -1));
  } else if (ev.key === "ArrowUp" && actual > 0 && !ev.altKey && !t.matches("textarea, select, input[type=number], input[type=radio]")) {
    ev.preventDefault(); irA(vecina(actual, -1));
  } else if (/^[a-z]$/i.test(ev.key) && !ev.ctrlKey && !ev.metaKey && !ev.altKey && !escribiendo(t)) {
    const o = q.querySelector(`.opcion[data-letra="${ev.key.toUpperCase()}"] input`);
    if (o) { ev.preventDefault(); o.click(); o.focus(); }
  }
});
irA(0, { foco: false, animar: false });

// Portada: la encuesta empieza con título, descripción y «Empezar»; al pulsarlo entra la primera pregunta.
const enInicio = () => $("#view-perfil").classList.contains("en-inicio");
function empezar() {
  const v = $("#view-perfil");
  if (!quieto.matches) {
    v.classList.add("saliendo");
    setTimeout(() => { v.classList.remove("saliendo"); irA(0); PANTALLAS[0].classList.add("entra"); }, 160);
  } else irA(0);
}
numerar();
// Idiomas: idioma + nivel (A1…C2 o Nativo) → «Inglés (C1)» en la lista.
$("#idioma-ok").addEventListener("click", () => {
  const box = $('.chipbox[data-for="idiomas"]'), idioma = $("#idioma-sel").value;
  const nivel = $("[name=_nivel]:checked")?.value || "B2";
  const vals = chipValores(box).filter((v) => !igual(v.replace(/\s*\(.*\)\s*$/, ""), idioma));  // cambia el nivel si ya estaba
  vals.push(`${idioma} (${nivel})`);
  chipCampo(box).value = vals.join("\n"); pintarChips(box);
});
$("#view-perfil").classList.add("en-inicio");
$("#q-empezar").addEventListener("click", empezar);

// -- sugerencias de habilidades y roles (sin IA: static/sugerencias.js + mapa local) --
// Declaradas como function: la encuesta pinta las sugerencias desde que carga la página.
function igual(a, b) { return Sugerencias.normalizar(a) === Sugerencias.normalizar(b); }
function alternar(campo, valor) {
  const box = $(`.chipbox[data-for="${campo}"]`), vals = chipValores(box);
  const i = vals.findIndex((v) => igual(v, valor));
  if (i >= 0) vals.splice(i, 1); else vals.push(valor);
  chipCampo(box).value = vals.join("\n");
  pintarChips(box);
}
function pintarSugerencias() {
  if (!$("#sug-roles")) return;
  const perfil = { ...perfilDelFormulario(), sugerencias: sugerenciasAgente };
  const s = Sugerencias.sugerir(perfil, window.SUGERENCIAS, ESCO);
  const tengo = (campo) => chipValores($(`.chipbox[data-for="${campo}"]`));
  const iAreas = [...document.querySelectorAll("#form-perfil .q")].findIndex((q) => q.querySelector("[name=intereses]"));
  const vacio = `<p class="hint">Elige tus <button type="button" class="linkbtn" data-paso-ir="${iAreas}">áreas de interés</button> para ver sugerencias.</p>`;
  const habs = tengo("habilidades");
  // Todas las habilidades de las áreas que elegiste (sin tope); si no elegiste ninguna, las sugeridas por tu trabajo.
  const elegidas = new Set((perfil.intereses || []).map(Sugerencias.normalizar));
  const deAreas = [];
  window.SUGERENCIAS.areas.filter((a) => elegidas.has(Sugerencias.normalizar(a.area)))
    .forEach((a) => a.habilidades.forEach((h) => { if (!deAreas.some((x) => igual(x, h))) deAreas.push(h); }));
  const lista = deAreas.length ? deAreas : s.habilidades.map((h) => h.nombre);
  $("#sug-habilidades").innerHTML = lista.length ? `<div class="sug-chips">${lista.map((h) => {
      const on = habs.some((x) => igual(x, h));
      return `<button type="button" class="sug-chip" aria-pressed="${on}" data-alternar="habilidades" data-valor="${esc(h)}">
        ${on ? "✓" : "+"} ${esc(h)}</button>`;
    }).join("")}</div>` : vacio;
  const roles = tengo("roles_objetivo");
  $("#sug-roles").innerHTML = s.roles.length ? `<div class="sug-chips">${s.roles.map((r) => {
      const on = roles.some((x) => igual(x, r.rol));
      return `<button type="button" class="sug-chip" aria-pressed="${on}" data-alternar="roles_objetivo" data-valor="${esc(r.rol)}"
        title="${esc(r.razon)}">${on ? "✓" : "+"} ${esc(r.rol)}</button>`;
    }).join("")}</div>` : vacio;
}
$("#form-perfil").addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-alternar]");
  if (b) alternar(b.dataset.alternar, b.dataset.valor);
  const ir = ev.target.closest("[data-paso-ir]");
  if (ir) irA(+ir.dataset.pasoIr);
});
$("#interes-otra").addEventListener("change", (ev) => {
  $("#otra-lbl").hidden = !ev.target.checked;
  if (ev.target.checked) $("#otra-lbl input").focus(); else $("#otra-lbl input").value = "";
});

// Lo que hay en el formulario ahora, sin tocarlo (para las sugerencias y para guardar).
function perfilDelFormulario() {
  const f = $("#form-perfil"), out = {};
  f.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name || el.name.startsWith("_") || el.name === "intereses" || (el.type === "radio" && !el.checked)) return;
    let v = el.type === "checkbox" ? el.checked : el.value.trim();
    if (LISTAS.includes(el.name)) v = v.split(/\n|;/).map((x) => x.trim()).filter(Boolean);
    const [a, b] = el.name.split(".");
    if (b) (out[a] ??= {})[b] = v; else out[a] = v;
  });
  out.intereses = [...f.querySelectorAll("input[name=intereses]:checked")].map((el) => el.value);
  if (!$("#interes-otra").checked) out.intereses_otra = "";
  return out;
}

function datosPerfil() {
  // Un chip escrito pero sin pulsar Enter también cuenta.
  document.querySelectorAll(".chipbox").forEach((box) => { const i = box.querySelector("input"); if (i) { agregarChips(box, i.value); i.value = ""; } });
  return perfilDelFormulario();
}

async function guardarPerfil() {
  const r = await api("/api/perfil", datosPerfil());
  llenarPerfil(r.perfil);
  return r;
}

function pintarBusqueda(b) {
  const caja = $("#progreso");
  caja.hidden = !b.corriendo && !b.resultado && !b.error && !b.registro.length;
  const pct = b.total ? Math.round((100 * b.hechas) / b.total) : 0;
  $("#prog-bar").style.width = `${b.corriendo ? Math.max(pct, 3) : 100}%`;
  $("#prog-texto").textContent = b.corriendo ? `· ${b.hechas} de ${b.total} empresas`
    : b.error ? "· con error" : b.resultado ? `· ${b.resultado.encontradas} vacantes, ${b.resultado.nuevas} nuevas` : "";
  $("#prog-log").textContent = (b.error ? b.error + "\n\n" : "") + b.registro.join("\n");
  $("#prog-log").scrollTop = $("#prog-log").scrollHeight;
  $("#btn-buscar").disabled = b.corriendo;
  $("#btn-buscar").textContent = b.corriendo ? "Revisando…" : "Guardar y revisar vacantes";
}

async function seguirBusqueda() {
  const b = await api("/api/buscar");
  pintarBusqueda(b);
  if (b.corriendo) { setTimeout(seguirBusqueda, 1500); return; }
  if (b.resultado) {
    await cargar();
    toast(`Listo: ${b.resultado.encontradas} vacantes abiertas (${b.resultado.nuevas} nuevas)`);
    mostrar("empresas");
  }
}

$("#form-perfil").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await guardarPerfil();
    if (!state.empresas.some((e) => e.url_empleos)) {
      toast("Perfil guardado. Aún no hay empresas con página de empleos: pídele a tu agente que las busque.");
      return;
    }
    pintarBusqueda(await api("/api/buscar", {}));
    seguirBusqueda();
  } catch (e) { toast(e.message); }
});

async function cargarPerfil() {
  const [, b] = await Promise.all([api("/api/perfil"), api("/api/buscar")]);
  // La encuesta empieza siempre en blanco: al recargar la página no se rellenan las respuestas anteriores.
  // (El perfil guardado sigue en la computadora para el agente; se reemplaza al terminar la encuesta.)
  if (!cargarPerfil.lista) {
    $("#form-perfil").querySelectorAll("[autocomplete]").forEach((el) => { el.autocomplete = "off"; });  // sin autocompletar del navegador
    $("#form-perfil").reset(); llenarPerfil({}); cargarPerfil.lista = true; }
  pintarBusqueda(b);
  if (b.corriendo) seguirBusqueda();
  const con = state.empresas.filter((e) => e.url_empleos).length;
  $("#buscar-info").textContent = state.empresas.length
    ? `Con «Guardar y revisar vacantes» se revisan ${con} páginas de empleo de tus ${state.empresas.length} empresas.`
    : "Para descubrir empresas donde podrías trabajar, pídele a tu agente: «Busca empresas en RD para mi perfil».";
}

// Botones «Copiar» fuera de la app (p. ej. el mensaje para instalar en la demo pública).
document.querySelectorAll("[data-copiar]").forEach((b) => b.addEventListener("click", async () => {
  const el = $(b.dataset.copiar);
  try { await navigator.clipboard.writeText(el.textContent.trim()); toast("Copiado"); }
  catch (_) { getSelection().selectAllChildren(el); toast("Selecciónalo y cópialo"); }
}));

// -- tema claro / oscuro (se recuerda en este navegador) ------------------------------
function ponerTema(t) {
  if (t === "oscuro") document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
  document.querySelectorAll("input[name=tema]").forEach((r) => { r.checked = r.value === t; });
  $("#btn-tema")?.setAttribute("aria-label", t === "oscuro" ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
  try { localStorage.setItem("tema", t); } catch (_) { /* sin almacenamiento */ }
}
document.querySelectorAll("input[name=tema]").forEach((r) => r.addEventListener("change", () => ponerTema(r.value)));
// Botón «Cambiar tema» de la barra de acciones.
$("#btn-tema")?.addEventListener("click", () => {
  ponerTema(document.documentElement.dataset.theme === "dark" ? "claro" : "oscuro");
});
ponerTema(document.documentElement.dataset.theme === "dark" ? "oscuro" : "claro");

// -- carga ----------------------------------------------------------------------------
async function cargar() {
  const [resumen, empresas, vacantes] = await Promise.all([api("/api/resumen"), api("/api/empresas"), api("/api/vacantes")]);
  Object.assign(state, { resumen, empresas, vacantes });
  const sel = $("#v-empresa"), actual = sel.value;
  const nombres = [...new Set(vacantes.map((v) => v.empresa_nombre).filter(Boolean))].sort();
  sel.innerHTML = `<option value="">Todas</option>` + nombres.map((n) => `<option ${n === actual ? "selected" : ""}>${esc(n)}</option>`).join("");
  pintarResumen(); pintarTablero(); pintarEmpresas(); pintarVacantes();
}

// Enlaces directos: #tablero, #empresas, #vacantes, #empresa-12
const hash = location.hash.slice(1);
if (["perfil", "resumen", "tablero", "empresas", "vacantes"].includes(hash)) mostrar(hash);
else { try { const v = localStorage.getItem("vista"); if (v) mostrar(v); } catch (_) { /* sin almacenamiento */ } }
cargar().then(() => {
  const m = hash.match(/^empresa-(\d+)$/);
  if (m) { mostrar("empresas"); abrir(+m[1]); }
  // Página de inicio: sin perfil o sin empresas todavía, empieza en «Mi perfil».
  else if (!hash && (!state.resumen.perfil_existe || !state.empresas.length)) mostrar("perfil");
  return cargarPerfil();
})
  .catch((e) => toast(e.message));
