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
const fit = (n, sufijo = "") => n == null ? `<span class="fit" title="Sin puntuar">–</span>`
  : `<span class="fit ${n >= 70 ? "hi" : n >= 50 ? "mid" : ""}" title="Ajuste con tu perfil">${n}%${sufijo}</span>`;
const ICONO_OK = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>';

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
  t.innerHTML = `${ICONO_OK}<span>${esc(msg)}</span>`;
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
// «Llenar mi perfil» y otros botones con data-ir: abre esa vista y sube a la ventana de la app.
document.querySelectorAll("[data-ir]").forEach((b) => b.addEventListener("click", () => {
  mostrar(b.dataset.ir);
  $("#app").scrollIntoView({ behavior: "smooth", block: "start" });
}));

// -- resumen --------------------------------------------------------------------------
function pintarResumen() {
  const { resumen: r, novedades: nov, perfil_existe } = state.resumen;
  $("#aviso-perfil").hidden = perfil_existe;
  const pe = r.por_estado;
  const tiles = [
    ["Vacantes", r.total_vacantes, `${r.total_empresas} empresas`],
    ["Me interesa", pe["Me interesa"], "elegidas por ti"],
    ["Aplicadas esta semana", r.aplicadas_semana, "desde el lunes", "accent"],
    ["Entrevistas", pe["Entrevista"], `${pe["Oferta"]} ofertas`, "green"],
    ["Seguimientos", r.seguimientos.length, "próximos 7 días"],
  ];
  $("#tiles").innerHTML = tiles.map(([k, v, s, tono]) =>
    `<div class="tile ${tono || ""}"><span>${esc(k)}</span><b>${v}</b><span>${esc(s)}</span></div>`).join("");
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
    return `<div class="col" data-estado="${esc(e)}"><h3><span style="--dot:var(--s-${CLASE_ESTADO[e]})">${esc(e)}</span><i>${vs.length}</i></h3>
      ${vs.map((v) => `<div class="kcard" draggable="true" data-id="${v.id}">
        <div class="t">${esc(v.titulo)}</div>
        <div class="c">${esc(v.empresa_nombre || "—")}${v.ubicacion ? ` · ${esc(v.ubicacion)}` : ""}</div>
        <div class="m">${fit(v.ajuste, " fit")}${v.alertas.length ? `<span class="warn" title="${esc(v.alertas.join(" · "))}">⚠ ${v.alertas.length} ${v.alertas.length === 1 ? "alerta" : "alertas"}</span>` : ""}</div>
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
      <td><b>${esc(v.titulo)}</b><span class="sub">${esc(v.empresa_nombre || "—")} · ${esc(v.ubicacion || "sin ubicación")} · ${fecha(v.primera_vez)}</span>
        ${v.alertas.length ? ` <span class="tag" title="${esc(v.alertas.join(" · "))}">⚠ ${v.alertas.length}</span>` : ""}${v.fuente === "pegado" ? ' <span class="tag">pegada</span>' : ""}</td>
      <td>${pill(v.estado)}</td><td>${fit(v.ajuste, " match")}</td>
      <td><button type="button" class="btn small">Ver detalle</button></td></tr>`).join("")
    || `<tr><td colspan="4" class="hint">No hay vacantes con estos filtros.</td></tr>`;
  document.querySelectorAll("#tbl-vacantes tbody tr[data-id]").forEach((tr) => tr.addEventListener("click", () => abrir(+tr.dataset.id)));
}
["#f-texto", "#f-min", "#f-empresa", "#f-estado", "#f-activas"].forEach((s) => $(s).addEventListener("input", pintarVacantes));

// -- empresas -------------------------------------------------------------------------
function pintarEmpresas() {
  const clase = (e) => ({ ok: "rs-ok", "revisar manualmente": "rs-warn", "abrir manualmente": "rs-warn", error: "rs-err" }[e] || "");
  $("#companies").innerHTML = state.empresas.map((e) => `<article class="company">
      <header><div class="c-logo" aria-hidden="true">${esc((e.nombre || "?").trim().charAt(0).toUpperCase())}</div>
        <div class="grow"><h3>${esc(e.nombre)}</h3><span class="sub">${esc(e.industria)}</span></div>
        <span class="count">${e.vacantes_activas} ${e.vacantes_activas === 1 ? "vacante" : "vacantes"}</span></header>
      <p class="why">${esc(e.por_que)}</p>
      <div class="interes" title="Interés ${e.interes}/100">Interés ${e.interes}<div class="meter"><i style="width:${+e.interes}%"></i></div></div>
      <div class="roles">${e.contactos.map((c) => `<a href="${safeUrl(c.linkedin)}" target="_blank" rel="noopener" title="Buscar en LinkedIn">${esc(c.rol)} ↗</a>`).join("")}</div>
      <div class="foot">
        <span class="pill ${clase(e.estado_rastreo)}">${esc(e.estado_rastreo)}</span>
        ${e.url_empleos ? `<a href="${safeUrl(e.url_empleos)}" target="_blank" rel="noopener">Página de empleos ↗</a>` : ""}
        ${e.sitio_web ? `<a href="${safeUrl(e.sitio_web)}" target="_blank" rel="noopener">Sitio web ↗</a>` : ""}
        ${e.ats ? `<span class="tag">${esc(e.ats)}</span>` : ""}
      </div>
      ${e.nota_rastreo && e.estado_rastreo !== "ok" ? `<div class="nota-rastreo">${esc(e.nota_rastreo)}</div>` : ""}
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
      ${texto ? `<button class="btn small" data-copy="${tipo}"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h9"/></svg>Copiar</button>` : ""}</span></header>
      ${texto ? `<textarea id="doc-${tipo}" rows="${tipo === "carta" ? 12 : 6}" readonly>${esc(texto)}</textarea>` : ""}</div>`;
  const n = v.ajuste;
  const [nivel, etiqueta] = n == null ? ["none", "Sin puntuar"] : n >= 70 ? ["hi", "Buen ajuste"] : n >= 50 ? ["mid", "Ajuste parcial"] : ["low", "Ajuste bajo"];
  $("#drawer-body").innerHTML = `
    <div class="d-head"><h2>${esc(v.titulo)}</h2><div class="sub">${esc(v.empresa_nombre || "Empresa sin registrar")} · ${esc(v.ubicacion || "sin ubicación")}</div>
      ${v.url ? `<div class="sub"><a href="${safeUrl(v.url)}" target="_blank" rel="noopener">Ver anuncio ↗</a></div>` : ""}</div>
    <div class="d-body">
    <div class="d-fit ${nivel}"><div><h3>Ajuste con tu perfil · ${etiqueta}</h3>
      <div class="sub">${v.fecha_publicacion ? `publicada ${fecha(v.fecha_publicacion + "T12:00")} · ` : ""}puntuado por ${esc(v.puntuado_por || "—")}</div></div>
      <b>${n == null ? "–" : n + "%"}</b></div>
    ${v.activa ? "" : '<p class="hint" style="margin:8px 0 0"><span class="tag">ya no aparece en la página</span></p>'}
    <div class="d-sec"><h3>Por qué encaja</h3>${lista(v.por_que_encaja, "good", "Sin puntuar todavía.")}</div>
    <div class="d-sec"><h3>Señales de alerta</h3>${lista(v.alertas, "warn", "Ninguna detectada.")}</div>
    ${(v.a_conversar || []).length ? `<div class="d-sec"><h3>A conversar</h3>${lista(v.a_conversar, "talk", "")}</div>` : ""}
    <div class="d-sec"><h3>Lo que me falta</h3>${lista(v.faltantes, "gap", "Nada evidente.")}</div>
    <div class="d-sec"><h3>Mensaje y carta</h3>
      ${puedeDocs ? "" : '<p class="hint">Marca la vacante «Me interesa» para preparar el mensaje y la carta.</p>'}
      ${doc("mensaje", "Mensaje corto (LinkedIn / correo)", v.mensaje)}
      ${doc("carta", "Carta de presentación", v.carta)}
      <p class="hint" style="margin-top:6px">Se guardan como archivos en <code>data/documentos</code>. Nada se envía solo.</p></div>
    ${v.contactos.length ? `<div class="d-sec"><h3>A quién contactar (roles)</h3><div class="roles">
      ${v.contactos.map((c) => `<a href="${safeUrl(c.linkedin)}" target="_blank" rel="noopener">${esc(c.rol)} ↗</a>`).join("")}</div></div>` : ""}
    <div class="d-sec"><h3>Notas</h3><textarea id="d-nota" rows="3" placeholder="Escribe aquí; se guarda solo">${esc(v.nota)}</textarea></div>
    <div class="d-sec"><h3>Descripción</h3><div class="desc">${esc(v.descripcion || "Sin descripción. Abre el anuncio.")}</div></div>
    <div class="d-sec"><h3>Historial</h3><ul class="timeline">${v.historial.map((h) => `<li>${esc(h.a_estado)}
      <div class="sub">${new Date(h.fecha).toLocaleString("es-DO")}${h.nota ? " · " + esc(h.nota) : ""}</div></li>`).join("")}</ul></div>
    </div>
    <div class="d-actions"><label>Mover a <select id="d-estado">${ESTADOS.map((e) => `<option ${e === v.estado ? "selected" : ""}>${esc(e)}</option>`).join("")}</select></label>
      <label>Seguimiento <input type="date" id="d-seg" value="${esc(v.seguimiento)}"></label></div>`;
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

// -- mi perfil (las 8 preguntas) y búsqueda -------------------------------------------
const LISTAS = ["roles_objetivo", "habilidades", "idiomas"];
const leer = (obj, ruta) => ruta.split(".").reduce((o, k) => (o ?? {})[k], obj);

function llenarPerfil(perfil) {
  const f = $("#form-perfil");
  f.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name) return;
    if (el.name === "industrias") { el.checked = (perfil.industrias || []).includes(el.value); return; }
    const v = leer(perfil, el.name);
    if (el.type === "checkbox") el.checked = !!v;
    else if (LISTAS.includes(el.name)) el.value = (v || []).join("\n");
    else el.value = v ?? "";
  });
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
  $("#btn-buscar").hidden = paso !== PASOS.length - 1;  // la búsqueda se lanza desde el último paso
  $("#wz-next").textContent = paso < PASOS.length - 1 ? "Continuar" : "";
}
$("#wz-steps").addEventListener("click", (ev) => { const b = ev.target.closest("[data-paso]"); if (b) irAPaso(+b.dataset.paso); });
$("#wz-prev").addEventListener("click", () => irAPaso(paso - 1));
$("#wz-next").addEventListener("click", () => irAPaso(paso + 1));
// Enter en un campo de texto avanza de paso en vez de lanzar la búsqueda.
$("#form-perfil").addEventListener("keydown", (ev) => {
  if (ev.key !== "Enter" || ev.target.tagName !== "INPUT" || ev.target.closest(".chipbox")) return;
  ev.preventDefault();
  if (paso < PASOS.length - 1) irAPaso(paso + 1);
});
irAPaso(0);

function datosPerfil() {
  const f = $("#form-perfil"), out = {};
  // Un chip escrito pero sin pulsar Enter también cuenta.
  document.querySelectorAll(".chipbox").forEach((box) => { const i = box.querySelector("input"); agregarChips(box, i.value); i.value = ""; });
  f.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name || el.name === "industrias") return;
    let v = el.type === "checkbox" ? el.checked : el.value.trim();
    if (LISTAS.includes(el.name)) v = v.split(/\n|;/).map((x) => x.trim()).filter(Boolean);
    const [a, b] = el.name.split(".");
    if (b) (out[a] ??= {})[b] = v; else out[a] = v;
  });
  out.industrias = [...f.querySelectorAll("input[name=industrias]:checked")].map((el) => el.value);
  return out;
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
  $("#btn-buscar").textContent = b.corriendo ? "Buscando…" : "Guardar y buscar";
}

async function seguirBusqueda() {
  const b = await api("/api/buscar");
  pintarBusqueda(b);
  if (b.corriendo) { setTimeout(seguirBusqueda, 1500); return; }
  if (b.resultado) {
    await cargar();
    toast(`Listo: ${b.resultado.encontradas} vacantes (${b.resultado.nuevas} nuevas)`);
    $("#f-estado").value = ""; pintarVacantes(); mostrar("vacantes");
  }
}

$("#btn-guardar").addEventListener("click", async () => {
  try { await guardarPerfil(); toast("Perfil guardado"); cargar(); } catch (e) { toast(e.message); }
});
$("#form-perfil").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await guardarPerfil();
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
  $("#buscar-info").textContent = `Se revisarán ${con} páginas de empleo de ${state.empresas.length} empresas guardadas.`;
}

// -- tema claro / oscuro (se recuerda en este navegador) ------------------------------
function ponerTema(t) {
  if (t === "oscuro") document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
  document.querySelectorAll("input[name=tema]").forEach((r) => { r.checked = r.value === t; });
  try { localStorage.setItem("tema", t); } catch (_) { /* sin almacenamiento */ }
}
document.querySelectorAll("input[name=tema]").forEach((r) => r.addEventListener("change", () => ponerTema(r.value)));
ponerTema(document.documentElement.dataset.theme === "dark" ? "oscuro" : "claro");

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
if (["perfil", "resumen", "tablero", "vacantes", "empresas"].includes(hash)) mostrar(hash);
else { try { const v = localStorage.getItem("vista"); if (v) mostrar(v); } catch (_) { /* sin almacenamiento */ } }
cargar().then(() => {
  const m = hash.match(/^vacante-(\d+)$/);
  if (m) { mostrar("tablero"); abrir(+m[1]); }
  // Página de inicio: sin perfil o sin ninguna búsqueda todavía, empieza en «Mi perfil».
  else if (!hash && (!state.resumen.perfil_existe || !state.resumen.novedades.corrida)) mostrar("perfil");
  return cargarPerfil();
})
  .catch((e) => toast(e.message));
