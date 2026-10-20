// Habilidades y roles sugeridos SIN IA, a partir del mapa local (oportunidades/sugerencias.json, que la página
// recibe en window.SUGERENCIAS). Es la misma lógica que oportunidades/sugerencias.py: tests/test_sugerencias.py
// comprueba con node que las dos den exactamente lo mismo. Si cambias una, cambia la otra.
"use strict";
(function (raiz) {
  const MAX_HABILIDADES = 12, MAX_ROLES = 8;
  const PESOS = { interes: 3, puesto_actual: 3, estudios: 2, otros: 1 };
  const FUERTE = 2;  // puntos mínimos para que un área entre en los primeros turnos

  // Minúsculas, sin tildes y sin signos: «Diseño UX/UI» → «diseno ux ui».
  const normalizar = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, " ").trim();
  const menciona = (texto, palabra) => ` ${texto} `.includes(` ${normalizar(palabra)}`);
  const coincide = (a, b) => {
    const na = normalizar(a), nb = normalizar(b);
    return !!(na && nb) && (` ${nb} `.includes(` ${na} `) || ` ${na} `.includes(` ${nb} `));
  };
  const lista = (v) => (Array.isArray(v) ? v : []);
  const limpio = (v) => String(v).trim().replace(/\.+$/, "");

  // Uno de cada grupo por vuelta: [[a1, a2], [b1]] → [a1, b1, a2].
  const turnos = (grupos) => {
    const out = [], largo = Math.max(0, ...grupos.map((g) => g.length));
    for (let k = 0; k < largo; k++) for (const g of grupos) if (k < g.length) out.push(g[k]);
    return out;
  };
  const porTurnos = (activas, elementos) => turnos(activas.filter((x) => x.puntos >= FUERTE).map(elementos))
    .concat(turnos(activas.filter((x) => x.puntos < FUERTE).map(elementos)));

  function razon(rol, fuentes, ya, perfil) {
    if (ya.length) return `Usa ${ya.slice(0, 2).join(" y ")}, que ya tienes.`;
    if (fuentes.includes("puesto_actual")) return `Encaja con tu experiencia como ${limpio(perfil.puesto_actual)}.`;
    if (fuentes.includes("estudios")) return `Encaja con lo que estudiaste (${limpio(perfil.estudios)}).`;
    return rol.razon;
  }

  function sugerir(perfil, mapa) {
    const intereses = new Set(lista(perfil.intereses).map(normalizar));
    const textos = {
      puesto_actual: normalizar(perfil.puesto_actual), estudios: normalizar(perfil.estudios),
      otros: normalizar(`${perfil.experiencia || ""} ${perfil.intereses_otra || ""}`),
    };
    const tengo = lista(perfil.habilidades).map(String);

    const activas = [];
    mapa.areas.forEach((area, i) => {
      const fuentes = intereses.has(normalizar(area.area)) ? ["interes"] : [];
      for (const [f, texto] of Object.entries(textos)) {
        if (texto && area.palabras.some((p) => menciona(texto, p))) fuentes.push(f);
      }
      if (fuentes.length) activas.push({ area, i, puntos: fuentes.reduce((s, f) => s + PESOS[f], 0), fuentes });
    });
    activas.sort((a, b) => b.puntos - a.puntos || a.i - b.i);

    const agente = perfil.sugerencias && typeof perfil.sugerencias === "object" && !Array.isArray(perfil.sugerencias) ? perfil.sugerencias : {};
    const habilidades = [], vistas = new Set();
    for (const [origen, nombres] of [["agente", lista(agente.habilidades)], ["mapa", porTurnos(activas, (x) => x.area.habilidades)]]) {
      for (const nombre of nombres) {
        const n = normalizar(nombre);
        if (n && !vistas.has(n) && (origen === "agente" || habilidades.filter((h) => h.origen === "mapa").length < MAX_HABILIDADES)) {
          vistas.add(n);
          habilidades.push({ nombre, origen });
        }
      }
    }

    const rolesDelArea = (x) => x.area.roles
      .map((rol, j) => ({ rol, j, fuentes: x.fuentes, ya: (rol.habilidades || []).filter((h) => tengo.some((t) => coincide(h, t))) }))
      .sort((a, b) => b.ya.length - a.ya.length || a.j - b.j);
    const candidatos = porTurnos(activas, rolesDelArea);
    const roles = [], vistos = new Set();
    for (const r of lista(agente.roles)) {
      const n = normalizar(r && r.rol);
      if (n && !vistos.has(n)) { vistos.add(n); roles.push({ rol: r.rol, razon: r.razon || "", origen: "agente" }); }
    }
    let deMapa = 0;
    for (const { rol, fuentes, ya } of candidatos) {
      const n = normalizar(rol.rol);
      if (!vistos.has(n) && deMapa < MAX_ROLES) {
        vistos.add(n); deMapa += 1;
        roles.push({ rol: rol.rol, razon: razon(rol, fuentes, ya, perfil), origen: "mapa" });
      }
    }
    return { areas: activas.map((x) => x.area.area), habilidades, roles };
  }

  const api = { sugerir, normalizar, coincide };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.Sugerencias = api;
})(typeof window !== "undefined" ? window : globalThis);
