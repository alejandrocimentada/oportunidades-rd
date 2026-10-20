// Habilidades y roles sugeridos SIN IA, a partir del mapa local (oportunidades/sugerencias.json, que la página
// recibe en window.SUGERENCIAS) y del índice de ESCO (static/esco.json, que se carga al abrir el paso 3).
// Es la misma lógica que oportunidades/sugerencias.py: tests/test_sugerencias.py y tests/test_esco.py comprueban
// con node que las dos den exactamente lo mismo. Si cambias una, cambia la otra.
"use strict";
(function (raiz) {
  const MAX_HABILIDADES = 12, MAX_ROLES = 8;
  const MAX_ESCO_HABILIDADES = 6, MAX_ESCO_ROLES = 4;
  const MAX_RESULTADOS = 8;
  const PESOS = { interes: 3, puesto_actual: 3, estudios: 2, otros: 1 };
  const FUERTE = 2;  // puntos mínimos para que un área entre en los primeros turnos
  const MIN_ETIQUETA_OCUPACION = 5;
  // Palabras que no cuentan como inicio de palabra en el buscador: «as» no debe encontrar «work as a team».
  const VACIAS = new Set("a al an and as at by con de del e el en for in la las los o of on or para por the to u un una y with".split(" "));

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
  const mayuscula = (t) => t.charAt(0).toUpperCase() + t.slice(1);
  const comparar = (a, b) => { for (let k = 0; k < a.length; k++) if (a[k] !== b[k]) return a[k] < b[k] ? -1 : 1; return 0; };

  // Uno de cada grupo por vuelta: [[a1, a2], [b1]] → [a1, b1, a2].
  const turnos = (grupos) => {
    const out = [], largo = Math.max(0, ...grupos.map((g) => g.length));
    for (let k = 0; k < largo; k++) for (const g of grupos) if (k < g.length) out.push(g[k]);
    return out;
  };
  // Turnos entre las áreas fuertes y el grupo extra (ESCO); las áreas débiles, después.
  const porTurnos = (activas, elementos, extra) => turnos(activas.filter((x) => x.puntos >= FUERTE).map(elementos)
    .concat(extra.length ? [extra] : [])).concat(turnos(activas.filter((x) => x.puntos < FUERTE).map(elementos)));

  function razon(rol, fuentes, ya, perfil) {
    if (ya.length) return `Usa ${ya.slice(0, 2).join(" y ")}, que ya tienes.`;
    if (fuentes.includes("puesto_actual")) return `Encaja con tu experiencia como ${limpio(perfil.puesto_actual)}.`;
    if (fuentes.includes("estudios")) return `Encaja con lo que estudiaste (${limpio(perfil.estudios)}).`;
    return rol.razon;
  }

  // -- ESCO: índice, buscador y ocupaciones -----------------------------------------------------
  function prepararEsco(datos) {
    const hn = datos.h.map(([es, en, sinonimos]) => [normalizar(es), normalizar(en), sinonimos.map(normalizar)]);
    const porNombre = new Map();
    hn.forEach(([es, en, sinonimos], i) => {
      for (const n of [es, en, ...sinonimos]) if (n && !porNombre.has(n)) porNombre.set(n, i);
    });
    // Nombres de ocupación separados por «/» («camarero/camarera» → «camarero», «camarera»), sin los muy cortos.
    const formas = (etiquetas) => etiquetas.flatMap((e) => e.split("/")).map(normalizar)
      .filter((n) => n.length >= MIN_ETIQUETA_OCUPACION);
    const on = datos.o.map(([es, en, alternativas]) => formas([es, en, ...alternativas]));
    const principal = datos.o.map(([es, en]) => new Set(formas([es, en])));
    return { h: datos.h, hn, o: datos.o, on, principal, porNombre, eq: datos.equivalencias || {} };
  }

  // El texto normalizado y, si tiene palabras de RD, también con las de ESCO: «contador» → «contable».
  function variantes(texto, esco) {
    const cambiado = texto.split(" ").map((p) => (Object.prototype.hasOwnProperty.call(esco.eq, p) ? esco.eq[p] : p)).join(" ");
    return cambiado === texto ? [texto] : [texto, cambiado];
  }
  // Para no repetir roles: ESCO escribe «enfermero/enfermera»; cada forma cuenta por separado.
  const partes = (r) => (r.origen === "esco" ? r.rol.split("/") : [r.rol]).map(normalizar).filter(Boolean);
  const repetido = (ps, nombre, aceptados) => aceptados.some(([n]) => ps.some((p) => ` ${n} `.includes(` ${p} `)))
    || aceptados.some(([, pa]) => pa.some((p) => ` ${nombre} `.includes(` ${p} `)));

  // 0: igual; 1: el nombre empieza por lo escrito; 2: otra palabra del nombre empieza por lo escrito (sin contar
  // «de», «as», etc.); -1: no coincide. Nunca a mitad de palabra: «ual» no encuentra «manual».
  function nivel(nombre, consulta) {
    if (nombre === consulta) return 0;
    if (nombre.startsWith(consulta)) return 1;
    const palabras = nombre.split(" ");
    return palabras.some((p, j) => j > 0 && !VACIAS.has(p) && palabras.slice(j).join(" ").startsWith(consulta)) ? 2 : -1;
  }

  // Autocompletar desde 2 letras, en español, inglés o sinónimos, sin tildes. Orden: igual a lo escrito, empieza
  // por lo escrito, una palabra empieza por lo escrito; dentro de cada grupo, primero los nombres y luego los
  // sinónimos, y de la más usada a la menos (el índice ya viene así: por número de ocupaciones de ESCO).
  function buscarHabilidades(consulta, esco, n = MAX_RESULTADOS) {
    const q = normalizar(consulta);
    if (!esco || q.length < 2) return [];
    const consultas = variantes(q, esco);
    const mejores = [];
    esco.hn.forEach(([es, en, sinonimos], i) => {
      let mejor = null;
      [es, en, ...sinonimos].forEach((t, k) => {
        for (const v of consultas) {
          const nv = t ? nivel(t, v) : -1;
          if (nv >= 0 && (!mejor || comparar([nv, k], mejor) < 0)) mejor = [nv, k];
        }
      });
      if (mejor) mejores.push([mejor[0], mejor[1] >= 2 ? 1 : 0, i, mejor[1]]);
    });
    mejores.sort(comparar);
    return mejores.slice(0, n).map(([, , i, k]) => {
      const [es, en, sinonimos] = esco.h[i];
      return { es, en, sinonimo: k >= 2 ? sinonimos[k - 2] : "" };
    });
  }

  // Roles y habilidades que ESCO sugiere: ocupaciones como su puesto, o que piden 2+ de sus habilidades.
  function deEsco(perfil, esco) {
    if (!esco) return [[], []];
    const tengo = new Set(lista(perfil.habilidades).map(normalizar).filter((n) => esco.porNombre.has(n))
      .map((n) => esco.porNombre.get(n)));
    const puestos = variantes(normalizar(perfil.puesto_actual), esco);
    const misRoles = new Set(lista(perfil.roles_objetivo).flatMap((r) => variantes(normalizar(r), esco)));
    const ocupaciones = [];
    esco.on.forEach((etiquetas, j) => {
      const enPuesto = etiquetas.filter((e) => puestos.some((p) => p && ` ${p} `.includes(` ${e} `)));
      const porPuesto = enPuesto.length > 0;
      const porRol = etiquetas.some((e) => misRoles.has(e));
      const comunes = esco.o[j][3].filter((i) => tengo.has(i));
      if (porPuesto || porRol || comunes.length >= 2) {
        // Su nombre principal en el puesto cuenta más que un nombre alternativo («contable» > «administrativo contable»).
        const principal = enPuesto.some((e) => esco.principal[j].has(e));
        const puntos = (porPuesto ? 100 : 0) + (principal ? 10 : 0) + (porRol ? 50 : 0) + comunes.length;
        ocupaciones.push({ clave: [-puntos, j], j, porPuesto, comunes });
      }
    });
    ocupaciones.sort((a, b) => comparar(a.clave, b.clave));

    const roles = [];
    for (const { j, porPuesto, comunes } of ocupaciones) {
      if (roles.length < MAX_ESCO_ROLES && (porPuesto || comunes.length >= 2)) {
        const r = porPuesto ? "Ocupación de ESCO parecida a tu trabajo actual."
          : `Según ESCO, pide ${comunes.slice(0, 2).map((i) => esco.h[i][0]).join(" y ")}, que ya tienes.`;
        roles.push({ rol: mayuscula(esco.o[j][0]), razon: r, origen: "esco" });
      }
    }
    const habilidades = [], vistas = new Set(tengo);
    for (const { j } of ocupaciones) {
      for (const i of esco.o[j][3]) {
        if (!vistas.has(i) && habilidades.length < MAX_ESCO_HABILIDADES) { vistas.add(i); habilidades.push(mayuscula(esco.h[i][0])); }
      }
    }
    return [roles, habilidades];
  }

  function sugerir(perfil, mapa, esco) {
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
    const [rolesEsco, habilidadesEsco] = deEsco(perfil, esco);

    const agente = perfil.sugerencias && typeof perfil.sugerencias === "object" && !Array.isArray(perfil.sugerencias) ? perfil.sugerencias : {};
    const habilidades = [], vistas = new Set();
    let sugeridas = 0;
    const candidatas = lista(agente.habilidades).map((h) => [h, "agente"]).concat(porTurnos(activas,
      (x) => x.area.habilidades.map((h) => [h, "mapa"]), habilidadesEsco.map((h) => [h, "esco"])));
    for (const [nombre, origen] of candidatas) {
      const n = normalizar(nombre);
      if (n && !vistas.has(n) && (origen === "agente" || sugeridas < MAX_HABILIDADES)) {
        vistas.add(n);
        if (origen !== "agente") sugeridas += 1;
        habilidades.push({ nombre, origen });
      }
    }

    const rolesDelArea = (x) => x.area.roles
      .map((rol, j) => ({ rol, j, ya: (rol.habilidades || []).filter((h) => tengo.some((t) => coincide(h, t))) }))
      .sort((a, b) => b.ya.length - a.ya.length || a.j - b.j)
      .map(({ rol, ya }) => ({ rol: rol.rol, razon: razon(rol, x.fuentes, ya, perfil), origen: "mapa" }));
    const candidatos = lista(agente.roles).filter((r) => r && typeof r === "object")
      .map((r) => ({ rol: r.rol || "", razon: r.razon || "", origen: "agente" }))
      .concat(porTurnos(activas, rolesDelArea, rolesEsco));
    const roles = [], aceptados = [];
    let sugeridos = 0;
    for (const r of candidatos) {
      const n = normalizar(r.rol), ps = partes(r);
      if (n && !repetido(ps, n, aceptados) && (r.origen === "agente" || sugeridos < MAX_ROLES)) {
        aceptados.push([n, ps]);
        if (r.origen !== "agente") sugeridos += 1;
        roles.push(r);
      }
    }
    return { areas: activas.map((x) => x.area.area), habilidades, roles };
  }

  const api = { sugerir, normalizar, coincide, prepararEsco, buscarHabilidades };
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.Sugerencias = api;
})(typeof window !== "undefined" ? window : globalThis);
