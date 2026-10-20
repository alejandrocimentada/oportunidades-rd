"""Operaciones completas que usan los scripts y el tablero: rastrear, puntuar, pegar."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from . import ajuste, ia, perfil as perfil_mod
from .crawler import Bloqueado, Fetcher, Prohibido
from .db import Store, ahora
from .exportar import exportar_seguro
from .extraer import (ATS, busqueda_successfactors, detectar_ats, enlace_ver_todas, extraer, fuera_de_rd, parse_feed,
                      texto_detalle)
from .texto import es_portal_bloqueado, idioma, limpiar_espacios

MAX_DETALLES = 10  # páginas de detalle por empresa (para leer la descripción)


def abrir_store(exportar_al_cambiar: bool = True) -> Store:
    return Store(after_change=(lambda s: exportar_seguro(s)) if exportar_al_cambiar else None)


# -- puntuar ------------------------------------------------------------------------------
def puntuar(store: Store, perfil: dict, vacante_id: int, llamadas: dict | None = None) -> dict:
    """Usa la IA del perfil si hay clave; si no (o si falla), la heurística local."""
    vac = store.get_vacante(vacante_id)
    emp = store.get_empresa(vac["empresa_id"]) if vac.get("empresa_id") else None
    datos = dict(vac, industria=(emp or {}).get("industria", ""))
    res = None
    if ia.disponible(perfil):
        try:
            res = ia.puntuar(perfil, datos, llamadas)
        except ia.IAError as exc:
            print(f"Aviso: {exc}. Uso la heurística local.", file=sys.stderr)
    res = res or ajuste.heuristica(perfil, datos)
    return store.guardar_puntuacion(vacante_id, res["ajuste"], res["por_que_encaja"], res["alertas"],
                                    res["faltantes"], res["puntuado_por"], res.get("a_conversar", []))


# -- pegar --------------------------------------------------------------------------------
def pegar(store: Store, perfil: dict, texto: str, url: str = "", empresa: str = "", titulo: str = "",
          ubicacion: str = "") -> tuple[dict, bool]:
    texto = limpiar_espacios(texto)
    if not texto:
        raise ValueError("El texto de la vacante está vacío.")
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    titulo = titulo or lineas[0][:140]
    emp = store.get_empresa(empresa) if empresa else None
    vac, nueva = store.upsert_vacante(titulo=titulo, empresa_id=emp["id"] if emp else None,
                                      empresa_nombre=emp["nombre"] if emp else empresa, ubicacion=ubicacion,
                                      url=url, descripcion=texto, fuente="pegado")
    if nueva or vac["ajuste"] is None:
        vac = puntuar(store, perfil, vac["id"])
    return vac, nueva


# -- rastrear -----------------------------------------------------------------------------
@dataclass
class InformeEmpresa:
    empresa: str
    estado: str
    motivo: str = ""
    nuevas: list = field(default_factory=list)
    total: int = 0
    enlace: str = ""


def _vacantes_de_empresa(fetcher: Fetcher, emp: dict, detalles: bool) -> tuple[list, str, str, str]:
    """Devuelve (vacantes, estado, motivo, ats)."""
    url = emp["url_empleos"]
    if es_portal_bloqueado(url):
        return [], "revisar manualmente", "Es un portal de empleo: no se rastrea. Usa scripts/pegar.py.", ""
    ats = detectar_ats(url)
    html = ""
    if not ats:
        resp = fetcher.get(url)
        html = resp.texto
        ats = detectar_ats(resp.url_final or url, html)
        if not ats:
            res = extraer(html, url, resp.status, resp.url_final)
            alterna = busqueda_successfactors(html, resp.url_final or url) if res.estado != "ok" else ""
            if alterna:  # SuccessFactors: la portada es JavaScript; su página de búsqueda es HTML público
                r2 = fetcher.get(alterna)
                res = extraer(r2.texto, alterna, r2.status, r2.url_final)
            lista = enlace_ver_todas(html, resp.url_final or url) if res.estado == "sin vacantes" else ""
            if lista:  # la portada no tiene vacantes pero enlaza a la lista completa: se sigue una vez
                if es_portal_bloqueado(lista):
                    return [], "revisar manualmente", f"La lista de vacantes está en un portal de empleo: {lista}", ""
                try:
                    r3 = fetcher.get(lista)
                except Prohibido:
                    return [], "revisar manualmente", f"robots.txt no permite leer la lista de vacantes: {lista}", ""
                ats = detectar_ats(r3.url_final or lista, r3.texto)
                if ats:
                    return _desde_ats(fetcher, ats)
                res = extraer(r3.texto, lista, r3.status, r3.url_final)
                if res.estado != "ok":
                    res.motivo = f"{res.motivo} (lista: {lista})"
            if res.estado != "ok":
                return [], res.estado, res.motivo, ""
            vacs = res.vacantes
            if detalles:
                for v in [v for v in vacs if not v.descripcion and not fuera_de_rd(v.ubicacion)][:MAX_DETALLES]:
                    try:
                        d = fetcher.get(v.url)
                        if d.status < 400:
                            v.descripcion = texto_detalle(d.texto)
                    except (Prohibido, Bloqueado):
                        continue
                    except Exception as exc:  # una página de detalle que falla no detiene el resto
                        print(f"  aviso: no se pudo leer {v.url}: {exc}", file=sys.stderr)
            return vacs, "ok", "", ""
    return _desde_ats(fetcher, ats)


def _desde_ats(fetcher: Fetcher, ats: ATS) -> tuple[list, str, str, str]:
    resp = fetcher.get(ats.feed)
    if resp.status >= 400:
        estado = "error" if resp.status in (404, 410) else "abrir manualmente"
        return [], estado, f"El feed público de {ats.nombre} respondió {resp.status}: abre {ats.pagina}", ats.nombre
    try:
        vacs = parse_feed(ats, resp.texto)
    except Exception as exc:
        return [], "abrir manualmente", f"No se pudo leer el feed de {ats.nombre} ({exc}).", ats.nombre
    if not vacs:
        return [], "sin vacantes", f"{ats.nombre}: no hay vacantes publicadas.", ats.nombre
    return vacs, "ok", f"Leído desde el feed público de {ats.nombre}.", ats.nombre


def rastrear(store: Store, perfil: dict, fetcher: Fetcher | None = None, solo: list | None = None,
             detalles: bool = True, puntuar_nuevas: bool = True, log=print) -> dict:
    fetcher = fetcher or Fetcher()
    corrida = store.iniciar_corrida()
    informes, manuales, fuera = [], [], []
    empresas = [e for e in store.empresas() if e["url_empleos"]]
    if solo:
        claves = {str(s).lower() for s in solo}
        empresas = [e for e in empresas if str(e["id"]) in claves or e["nombre"].lower() in claves]
    for emp in empresas:
        log(f"· {emp['nombre']}: {emp['url_empleos']}")
        try:
            vacs, estado, motivo, ats = _vacantes_de_empresa(fetcher, emp, detalles)
        except Prohibido as exc:
            vacs, estado, ats = [], "revisar manualmente", ""
            motivo = f"robots.txt no permite leer {exc}. Ábrela tú en el navegador."
        except Bloqueado:
            vacs, estado, motivo, ats = [], "revisar manualmente", "Portal de empleo: usa scripts/pegar.py.", ""
        except Exception as exc:
            vacs, estado, motivo, ats = [], "error", f"No se pudo descargar: {exc}", ""
        omitidas = sum(1 for v in vacs if fuera_de_rd(v.ubicacion))
        if omitidas:
            vacs = [v for v in vacs if not fuera_de_rd(v.ubicacion)]
            motivo = f"{motivo} {omitidas} vacantes fuera de RD y no remotas, omitidas.".strip()
            if not vacs and estado == "ok":
                estado = "sin vacantes"
        inf = InformeEmpresa(emp["nombre"], estado, motivo, total=len(vacs), enlace=emp["url_empleos"])
        for v in vacs:
            vac, nueva = store.upsert_vacante(
                titulo=v.titulo, empresa_id=emp["id"], empresa_nombre=emp["nombre"], ubicacion=v.ubicacion,
                url=v.url, fecha_publicacion=v.fecha, descripcion=v.descripcion,
                fuente=f"ats:{ats}" if ats else "rastreo", corrida_id=corrida, commit=False)
            if nueva:
                inf.nuevas.append(vac["id"])
        store.conn.commit()
        if estado in ("ok", "sin vacantes"):
            fuera += [v["id"] for v in store.marcar_no_vistas(emp["id"], corrida)]
        else:
            manuales.append({"empresa": emp["nombre"], "estado": estado, "motivo": motivo, "enlace": emp["url_empleos"]})
        store.conn.execute("UPDATE empresas SET estado_rastreo = ?, nota_rastreo = ?, ats = ?, ultimo_rastreo = ?"
                           " WHERE id = ?", (estado, motivo, ats, ahora(), emp["id"]))
        store.conn.commit()
        log(f"  → {estado}: {len(vacs)} vacantes, {len(inf.nuevas)} nuevas. {motivo}".rstrip())
        informes.append(inf)
    if puntuar_nuevas:
        for inf in informes:
            for vid in inf.nuevas:
                v = store.get_vacante(vid)
                if v["idioma"] != idioma(v["titulo"] + "\n" + v["descripcion"]):
                    store.conn.execute("UPDATE vacantes SET idioma = ? WHERE id = ?",
                                       (idioma(v["titulo"] + "\n" + v["descripcion"]), vid))
                ajuste_cb = store.after_change
                store.after_change = None  # exportamos una sola vez al final
                try:
                    puntuar(store, perfil, vid)
                finally:
                    store.after_change = ajuste_cb
    resumen = {
        "empresas": len(informes),
        "nuevas": sum(len(i.nuevas) for i in informes),
        "encontradas": sum(i.total for i in informes),
        "ya_no_aparecen": fuera,
        "manuales": manuales,
    }
    store.terminar_corrida(corrida, resumen)
    return store.novedades(corrida)


def cargar_perfil() -> dict:
    return perfil_mod.cargar()
