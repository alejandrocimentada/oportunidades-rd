// Tablero de Oportunidades RD. Sin dependencias externas.
// Todo el texto viene de páginas de terceros: siempre se escapa antes de mostrarlo.
"use strict";

const ESTADOS = window.ESTADOS;
const CLASE_ESTADO = {
  "Nuevo": "nuevo", "Me interesa": "interesa", "Aplicado": "aplicado", "Contacté": "contacte",
  "Entrevista": "entrevista", "Oferta": "oferta", "Rechazado": "rechazado", "Descartado": "descartado",
};
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "#");
const fecha = (iso) => (iso ? new Date(iso).toLocaleDateString("es-DO", { day: "numeric", month: "short" }) : "");
const pill = (estado) => `<span class="pill" style="background:var(--s-${CLASE_ESTADO[estado] || "nuevo"})">${esc(estado)}</span>`;
const fit = (n) => n == null ? `<span class="fit" title="Sin puntuar">–</span>`
  : `<span class="fit ${n >= 70 ? "hi" : n >= 50 ? "mid" : ""}" title="Ajuste con tu perfil">${n}</span>`;

let state = { vacantes: [], empresas: [], resumen: null, abierta: null };

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2200);
}

// -- navegación -----------------------------------------------------------------------
function mostrar(view) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("on", v.id === `view-${view}`));
  try { localStorage.setItem("vista", view); } catch (_) { /* sin almacenamiento */ }
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => mostrar(b.dataset.view)));

// -- resumen --------------------------------------------------------------------------
function pintarResumen() {
  const { resumen: r, novedades: nov, perfil_existe } = state.resumen;
  $("#aviso-perfil").hidden = perfil_existe;
  const pe = r.por_estado;
  const tiles = [
    ["Vacantes", r.total_vacantes, `${r.total_empresas} empresas`],
    ["Me interesa", pe["Me interesa"], "elegidas por ti", true],
    ["Aplicaciones esta semana", r.aplicadas_semana, "desde el lunes"],
    ["Entrevistas", pe["Entrevista"], `${pe["Oferta"]} ofertas`],
    ["Seguimientos", r.seguimientos.length, "próximos 7 días"],
  ];
  $("#tiles").innerHTML = tiles.map(([k, v, s, hl]) =>
    `<div class="tile ${hl ? "hl" : ""}"><span>${esc(k)}</span><b>${v}</b><span>${esc(s)}</span></div>`).join("");
  $("#pipeline").innerHTML = ESTADOS.map((e) =>
    `<div data-estado="${esc(e)}" style="background:var(--s-${CLASE_ESTADO[e]})"><b>${pe[e]}</b>${esc(e)}</div>`).join("");
  document.querySelectorAll("#pipeline div").forEach((d) => d.addEventListener("click", () => {
    $("#f-estado").value = d.dataset.estado; pintarVacantes(); mostrar("vacantes");
  }));

  $("#nov-fecha").textContent = nov.corrida ? `· rastreo del ${new Date(nov.corrida.inicio).toLocaleString("es-DO")}` : "";
  const items = nov.nuevas.map((v) => `<li data-id="${v.id}">${fit(v.ajuste)}<div class="grow"><div>${esc(v.titulo)}</div>
      <div class="sub">${esc(v.empresa_nombre)} · ${esc(v.ubicacion || "sin ubicación")}</div></div>${pill(v.estado)}</li>`);
  items.push(...nov.ya_no_aparecen.map((v) => `<li data-id="${v.id}"><span class="tag">ya no aparece</span>
      <div class="grow">${esc(v.titulo)}<div class="sub">${esc(v.empresa_nombre)}</div></div></li>`));
  $("#novedades").innerHTML = items.join("") || `<li class="empty">${nov.corrida ? "Nada nuevo desde el rastreo anterior." : "Todavía no hay rastreos: corre python scripts/rastrear.py"}</li>`;

  $("#seguimientos").innerHTML = r.seguimientos.map((v) => `<li data-id="${v.id}"><div class="grow">${esc(v.titulo)}
      <div class="sub">${esc(v.empresa_nombre)} · ${esc(v.estado)}</div></div>
      <span class="${v.vencido ? "overdue" : "sub"}">${v.vencido ? "vencido " : ""}${fecha(v.seguimiento + "T12:00")}</span></li>`).join("")
    || `<li class="empty">Nada pendiente.</li>`;
  $("#manuales").innerHTML = (nov.manuales || []).map((m) => `<li class="static"><b>${esc(m.empresa)}</b>
      <span class="tag">${esc(m.estado)}</span><div class="sub">${esc(m.motivo)}</div>
      <a href="${safeUrl(m.enlace)}" target="_blank" rel="noopener">Abrir página de empleos ↗</a></li>`).join("")
    || `<li class="empty">Nada que revisar a mano.</li>`;
  document.querySelectorAll("#novedades li[data-id], #seguimientos li[data-id]").forEach((li) =>
    li.addEventListener("click", () => abrir(+li.dataset.id)));
}

// -- tablero (kanban) -----------------------------------------------------------------
function pintarTablero() {
  const activas = state.vacantes.filter((v) => v.activa || v.estado !== "Nuevo");
  $("#board").innerHTML = ESTADOS.map((e) => {
    const vs = activas.filter((v) => v.estado === e);
    return `<div class="col" data-estado="${esc(e)}"><h3>${pill(e)}<i>${vs.length}</i></h3>
      ${vs.map((v) => `<div class="kcard" draggable="true" data-id="${v.id}">
        <div class="t">${esc(v.titulo)}</div><div class="c">${esc(v.empresa_nombre || "—")}</div>
        <div class="m">${fit(v.ajuste)}${v.alertas.length ? `<span class="warn" title="${esc(v.alertas.join(" · "))}">⚠ ${v.alertas.length}</span>` : ""}</div>
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
  const v = state.vacantes.find((x) => x.id === id);
  if (!v || v.estado === estado) return;
  try {
    await api(`/api/vacantes/${id}/estado`, { estado });
    toast(`«${v.titulo}» → ${estado}`);
    await cargar();
    if (state.abierta === id) abrir(id);
  } catch (e) { toast(e.message); }
}

// -- vacantes (lista) -----------------------------------------------------------------
function pintarVacantes() {
  const texto = $("#f-texto").value.toLowerCase();
  const min = +$("#f-min").value;
  const emp = $("#f-empresa").value;
  const est = $("#f-estado").value;
  const solo = $("#f-activas").checked;
  $("#f-min-out").textContent = min;
  const vs = state.vacantes.filter((v) =>
    (v.ajuste ?? 0) >= min && (!emp || v.empresa_nombre === emp) && (!est || v.estado === est) && (!solo || v.activa)
    && (!texto || `${v.titulo} ${v.empresa_nombre}`.toLowerCase().includes(texto)));
  $("#tbl-vacantes tbody").innerHTML = vs.map((v) => `<tr data-id="${v.id}" class="${v.activa ? "" : "inactive"}">
      <td>${fit(v.ajuste)}</td><td><b>${esc(v.titulo)}</b>${v.alertas.length ? ` <span class="tag" title="${esc(v.alertas.join(" · "))}">⚠ ${v.alertas.length}</span>` : ""}</td>
      <td>${esc(v.empresa_nombre)}</td><td>${pill(v.estado)}</td><td>${esc(v.ubicacion)}</td>
      <td>${fecha(v.primera_vez)}${v.fuente === "pegado" ? ' <span class="tag">pegada</span>' : ""}</td></tr>`).join("")
    || `<tr><td colspan="6" class="hint">No hay vacantes con estos filtros.</td></tr>`;
  document.querySelectorAll("#tbl-vacantes tbody tr[data-id]").forEach((tr) => tr.addEventListener("click", () => abrir(+tr.dataset.id)));
}
["#f-texto", "#f-min", "#f-empresa", "#f-estado", "#f-activas"].forEach((s) => $(s).addEventListener("input", pintarVacantes));

// -- empresas -------------------------------------------------------------------------
function pintarEmpresas() {
  const clase = (e) => ({ ok: "rs-ok", "revisar manualmente": "rs-warn", "abrir manualmente": "rs-warn", error: "rs-err" }[e] || "");
  $("#companies").innerHTML = state.empresas.map((e) => `<article class="company">
      <header><div><h3>${esc(e.nombre)}</h3><span class="tag">${esc(e.industria)}</span></div>
        <div title="Interés ${e.interes}/100"><div class="sub" style="font-size:12px;color:var(--muted)">Interés ${e.interes}</div>
        <div class="meter"><i style="width:${+e.interes}%"></i></div></div></header>
      <p class="why">${esc(e.por_que)}</p>
      <div class="roles">${e.contactos.map((c) => `<a href="${safeUrl(c.linkedin)}" target="_blank" rel="noopener" title="Buscar en LinkedIn">${esc(c.rol)} ↗</a>`).join("")}</div>
      <div class="foot">
        <span class="pill ${clase(e.estado_rastreo)}">${esc(e.estado_rastreo)}</span>
        <span>${e.vacantes_activas} ${e.vacantes_activas === 1 ? "vacante activa" : "vacantes activas"}</span>
        ${e.url_empleos ? `<a href="${safeUrl(e.url_empleos)}" target="_blank" rel="noopener">Página de empleos ↗</a>` : ""}
        ${e.sitio_web ? `<a href="${safeUrl(e.sitio_web)}" target="_blank" rel="noopener">Sitio web ↗</a>` : ""}
        ${e.ats ? `<span class="tag">${esc(e.ats)}</span>` : ""}
      </div>
      ${e.nota_rastreo && e.estado_rastreo !== "ok" ? `<div class="sub" style="font-size:12.5px;color:var(--warn)">${esc(e.nota_rastreo)}</div>` : ""}
    </article>`).join("") || `<p class="hint">Todavía no hay empresas. Pídele a tu agente que las busque.</p>`;
}

// -- detalle --------------------------------------------------------------------------
async function abrir(id) {
  const v = await api(`/api/vacantes/${id}`);
  state.abierta = id;
  const puedeDocs = state.resumen.con_documentos.includes(v.estado);
  const lista = (xs, cls, vacio) => xs.length ? `<div class="box ${cls}"><ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`
    : `<div class="box none">${vacio}</div>`;
  const doc = (tipo, titulo, texto) => `<div class="doc"><header>${titulo}
      <span><button class="btn small ghost" data-gen="${tipo}" ${puedeDocs ? "" : "disabled"}>${texto ? "Rehacer" : "Preparar"}</button>
      ${texto ? `<button class="btn small" data-copy="${tipo}">Copiar</button>` : ""}</span></header>
      ${texto ? `<textarea id="doc-${tipo}" rows="${tipo === "carta" ? 12 : 6}" readonly>${esc(texto)}</textarea>` : ""}</div>`;
  $("#drawer-body").innerHTML = `
    <div class="d-head"><div class="ring" style="--p:${v.ajuste ?? 0}"><b>${v.ajuste ?? "–"}</b></div>
      <div><h2>${esc(v.titulo)}</h2><div class="sub">${esc(v.empresa_nombre || "Empresa sin registrar")} · ${esc(v.ubicacion || "sin ubicación")}</div>
      <div class="sub">${v.url ? `<a href="${safeUrl(v.url)}" target="_blank" rel="noopener">Ver anuncio ↗</a> · ` : ""}
        ${v.fecha_publicacion ? `publicada ${fecha(v.fecha_publicacion + "T12:00")} · ` : ""}puntuado por ${esc(v.puntuado_por || "—")}</div></div></div>
    <div class="d-row"><label>Estado <select id="d-estado">${ESTADOS.map((e) => `<option ${e === v.estado ? "selected" : ""}>${esc(e)}</option>`).join("")}</select></label>
      <label>Seguimiento <input type="date" id="d-seg" value="${esc(v.seguimiento)}"></label>
      ${v.activa ? "" : '<span class="tag">ya no aparece en la página</span>'}</div>
    <div class="d-sec"><h3>Por qué encaja</h3>${lista(v.por_que_encaja, "good", "Sin puntuar todavía.")}</div>
    <div class="d-sec"><h3>Señales de alerta</h3>${lista(v.alertas, "warn", "Ninguna detectada.")}</div>
    ${(v.a_conversar || []).length ? `<div class="d-sec"><h3>A conversar</h3>${lista(v.a_conversar, "talk", "")}</div>` : ""}
    <div class="d-sec"><h3>Lo que me falta</h3>${lista(v.faltantes, "gap", "Nada evidente.")}</div>
    <div class="d-sec"><h3>Mensaje y carta</h3>
      ${puedeDocs ? "" : '<p class="hint">Marca la vacante «Me interesa» para preparar el mensaje y la carta.</p>'}
      ${doc("mensaje", "Mensaje corto (LinkedIn / correo)", v.mensaje)}
      ${doc("carta", "Carta de presentación", v.carta)}
      <p class="hint" style="margin-top:6px">Se guardan como archivos en <code>data/documentos</code>. Nada se envía solo.</p></div>
    ${v.contactos.length ? `<div class="d-sec"><h3>A quién contactar (roles)</h3><div class="company" style="border:0;padding:0"><div class="roles">
      ${v.contactos.map((c) => `<a href="${safeUrl(c.linkedin)}" target="_blank" rel="noopener">${esc(c.rol)} ↗</a>`).join("")}</div></div></div>` : ""}
    <div class="d-sec"><h3>Notas</h3><textarea id="d-nota" rows="3" placeholder="Escribe aquí; se guarda solo">${esc(v.nota)}</textarea></div>
    <div class="d-sec"><h3>Descripción</h3><div class="desc">${esc(v.descripcion || "Sin descripción. Abre el anuncio.")}</div></div>
    <div class="d-sec"><h3>Historial</h3><ul class="timeline">${v.historial.map((h) => `<li>${esc(h.a_estado)}
      <div class="sub">${new Date(h.fecha).toLocaleString("es-DO")}${h.nota ? " · " + esc(h.nota) : ""}</div></li>`).join("")}</ul></div>`;
  $("#d-estado").addEventListener("change", (ev) => cambiarEstado(id, ev.target.value));
  $("#d-seg").addEventListener("change", async (ev) => {
    try { await api(`/api/vacantes/${id}/seguimiento`, { fecha: ev.target.value }); toast("Seguimiento guardado"); cargar(); } catch (e) { toast(e.message); }
  });
  $("#d-nota").addEventListener("change", async (ev) => {
    try { await api(`/api/vacantes/${id}/nota`, { nota: ev.target.value }); toast("Nota guardada"); } catch (e) { toast(e.message); }
  });
  document.querySelectorAll("[data-gen]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true; b.textContent = "Preparando…";
    try { const r = await api(`/api/vacantes/${id}/generar`, { tipo: b.dataset.gen }); toast(`Listo (${r.origen})`); abrir(id); }
    catch (e) { toast(e.message); b.disabled = false; b.textContent = "Preparar"; }
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

// -- carga ----------------------------------------------------------------------------
async function cargar() {
  const [resumen, vacantes, empresas] = await Promise.all([api("/api/resumen"), api("/api/vacantes"), api("/api/empresas")]);
  Object.assign(state, { resumen, vacantes, empresas });
  const sel = $("#f-empresa"), actual = sel.value;
  const nombres = [...new Set(vacantes.map((v) => v.empresa_nombre).filter(Boolean))].sort();
  sel.innerHTML = `<option value="">Todas</option>` + nombres.map((n) => `<option ${n === actual ? "selected" : ""}>${esc(n)}</option>`).join("");
  pintarResumen(); pintarTablero(); pintarVacantes(); pintarEmpresas();
}

// Enlaces directos: #tablero, #vacantes, #empresas, #vacante-12
const hash = location.hash.slice(1);
if (["resumen", "tablero", "vacantes", "empresas"].includes(hash)) mostrar(hash);
else { try { const v = localStorage.getItem("vista"); if (v) mostrar(v); } catch (_) { /* sin almacenamiento */ } }
cargar().then(() => { const m = hash.match(/^vacante-(\d+)$/); if (m) { mostrar("tablero"); abrir(+m[1]); } })
  .catch((e) => toast(e.message));
