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

// -- mi perfil (8 pasos) y revisión de vacantes ---------------------------------------
const LISTAS = ["roles_objetivo", "habilidades", "idiomas"];
const leer = (obj, ruta) => ruta.split(".").reduce((o, k) => (o ?? {})[k], obj);
let sugerenciasAgente = {};  // las que el agente refinó (perfil.sugerencias); van primero
let ESCO = null;  // índice local de ESCO (static/esco.json), preparado al abrir el paso 3

function llenarPerfil(perfil) {
  const f = $("#form-perfil");
  f.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name) return;
    if (el.name === "intereses") { el.checked = (perfil.intereses || []).includes(el.value); return; }
    const v = leer(perfil, el.name);
    if (el.type === "checkbox") el.checked = !!v;
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
  box.innerHTML = `<div class="add"><input id="chip-${box.dataset.for}" placeholder="${esc(box.dataset.placeholder)}">
    <button type="button" class="btn">Añadir</button></div><div class="list-chips"></div>`;
  const input = box.querySelector("input");
  const agregar = () => { agregarChips(box, input.value); input.value = ""; input.focus(); };
  box.querySelector(".add button").addEventListener("click", agregar);
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); agregar(); }
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

// -- buscador de habilidades (paso 3): índice local (ESCO + habilidades curadas), funciona sin conexión ----
// Se carga una sola vez, al abrir los pasos 3 o 4; mientras tanto el campo acepta texto libre.
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

// Asistente: un paso visible a la vez, con barra de progreso y saltos directos a cualquier paso.
const PASOS = [...document.querySelectorAll("#form-perfil .step")];
let paso = 0;
function irAPaso(i) {
  paso = Math.max(0, Math.min(PASOS.length - 1, i));
  PASOS.forEach((s, j) => s.classList.toggle("on", j === paso));
  $("#wz-paso").textContent = `Paso ${paso + 1} de ${PASOS.length}`;
  $("#wz-titulo").textContent = PASOS[paso].dataset.titulo;
  const pct = Math.round(((paso + 1) / PASOS.length) * 100);
  $("#wz-bar").style.width = `${pct}%`;
  $("#wz-pct").textContent = `Progreso: ${pct}%`;
  $("#wz-steps").innerHTML = PASOS.map((s, j) => `<li><button type="button" data-paso="${j}"
      class="${j < paso ? "hecho" : j === paso ? "actual" : ""}" ${j === paso ? 'aria-current="step"' : ""}>
      <i>${j < paso ? "✓" : j + 1}</i>${esc(s.dataset.corto)}</button></li>`).join("");
  $("#wz-prev").disabled = paso === 0;
  $("#wz-next").hidden = paso === PASOS.length - 1;
  $("#btn-buscar").hidden = paso !== PASOS.length - 1;  // la revisión se lanza desde el último paso
  $("#wz-next").textContent = paso < PASOS.length - 1 ? "Continuar" : "";
  if (PASOS[paso].querySelector(".sug")) cargarEsco();  // pasos 3 y 4
  pintarSugerencias();
}
$("#wz-steps").addEventListener("click", (ev) => { const b = ev.target.closest("[data-paso]"); if (b) irAPaso(+b.dataset.paso); });
$("#wz-prev").addEventListener("click", () => irAPaso(paso - 1));
$("#wz-next").addEventListener("click", () => irAPaso(paso + 1));
// Enter en un campo de texto avanza de paso en vez de lanzar la revisión.
$("#form-perfil").addEventListener("keydown", (ev) => {
  if (ev.key !== "Enter" || ev.target.tagName !== "INPUT" || ev.target.closest(".chipbox")) return;
  ev.preventDefault();
  if (paso < PASOS.length - 1) irAPaso(paso + 1);
});
irAPaso(0);

// -- sugerencias de habilidades y roles (sin IA: static/sugerencias.js + mapa local) --
// Declaradas como function: el asistente pinta las sugerencias desde que carga la página.
function igual(a, b) { return Sugerencias.normalizar(a) === Sugerencias.normalizar(b); }
function alternar(campo, valor) {
  const box = $(`.chipbox[data-for="${campo}"]`), vals = chipValores(box);
  const i = vals.findIndex((v) => igual(v, valor));
  if (i >= 0) vals.splice(i, 1); else vals.push(valor);
  chipCampo(box).value = vals.join("\n");
  pintarChips(box);
}
function deAgente(s) {
  return { agente: ' <span class="tag">tu agente</span>', esco: ' <span class="tag" title="Clasificación europea ESCO">ESCO</span>' }[s.origen] || "";
}
function pintarSugerencias() {
  if (!$("#sug-roles")) return;
  const perfil = { ...perfilDelFormulario(), sugerencias: sugerenciasAgente };
  const s = Sugerencias.sugerir(perfil, window.SUGERENCIAS, ESCO);
  const tengo = (campo) => chipValores($(`.chipbox[data-for="${campo}"]`));
  const vacio = `<p class="hint">Elige tus áreas en el <button type="button" class="linkbtn" data-paso-ir="0">paso 1</button>
    o cuenta tu experiencia en el <button type="button" class="linkbtn" data-paso-ir="1">paso 2</button> para ver sugerencias.</p>`;
  const habs = tengo("habilidades");
  $("#sug-habilidades").innerHTML = s.habilidades.length ? `<p class="sug-t">Sugeridas para ti · toca para añadir o quitar</p>
    <div class="sug-chips">${s.habilidades.map((h) => {
      const on = habs.some((x) => igual(x, h.nombre));
      return `<button type="button" class="sug-chip" aria-pressed="${on}" data-alternar="habilidades" data-valor="${esc(h.nombre)}">
        ${on ? "✓" : "+"} ${esc(h.nombre)}${deAgente(h)}</button>`;
    }).join("")}</div>` : vacio;
  const roles = tengo("roles_objetivo");
  $("#sug-roles").innerHTML = s.roles.length ? `<p class="sug-t">Según tus intereses, experiencia y habilidades · toca para elegir</p>
    <div class="sug-roles">${s.roles.map((r) => {
      const on = roles.some((x) => igual(x, r.rol));
      return `<button type="button" class="sug-rol" aria-pressed="${on}" data-alternar="roles_objetivo" data-valor="${esc(r.rol)}">
        <i aria-hidden="true">${on ? "✓" : "+"}</i><span><b>${esc(r.rol)}${deAgente(r)}</b><small>${esc(r.razon)}</small></span></button>`;
    }).join("")}</div>` : vacio;
}
$("#form-perfil").addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-alternar]");
  if (b) alternar(b.dataset.alternar, b.dataset.valor);
  const ir = ev.target.closest("[data-paso-ir]");
  if (ir) irAPaso(+ir.dataset.pasoIr);
});
$("#interes-otra").addEventListener("change", (ev) => {
  $("#otra-lbl").hidden = !ev.target.checked;
  if (ev.target.checked) $("#otra-lbl input").focus(); else $("#otra-lbl input").value = "";
});

// Lo que hay en el formulario ahora, sin tocarlo (para las sugerencias y para guardar).
function perfilDelFormulario() {
  const f = $("#form-perfil"), out = {};
  f.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name || el.name === "intereses") return;
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
  document.querySelectorAll(".chipbox").forEach((box) => { const i = box.querySelector("input"); agregarChips(box, i.value); i.value = ""; });
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

$("#btn-guardar").addEventListener("click", async () => {
  try { await guardarPerfil(); toast("Perfil guardado"); cargar(); } catch (e) { toast(e.message); }
});
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
  const [{ perfil }, b] = await Promise.all([api("/api/perfil"), api("/api/buscar")]);
  llenarPerfil(perfil);
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
