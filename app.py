#!/usr/bin/env python3
"""Tablero local de Oportunidades RD.

    python app.py            → abre http://localhost:8765 en tu navegador

Solo escucha en tu computadora (127.0.0.1): nadie más en la red puede verlo.
"""
from __future__ import annotations

import argparse
import ipaddress
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from flask import Flask, abort, jsonify, render_template, request, send_file  # noqa: E402

from oportunidades import NOMBRE, config, ia, perfil as pf, redaccion  # noqa: E402
from oportunidades.contactos import contactos  # noqa: E402
from oportunidades.db import ESTADOS, ESTADOS_CON_DOCUMENTOS, INDUSTRIAS, DatosError  # noqa: E402
from oportunidades.exportar import exportar  # noqa: E402
from oportunidades.busqueda import Busqueda, BusquedaEnCurso  # noqa: E402
from oportunidades.servicio import abrir_store  # noqa: E402

HOST, PUERTO = "127.0.0.1", 8765
HOSTS_PERMITIDOS = {"localhost", "127.0.0.1"}


# Campos del perfil que la página «Mi perfil» puede cambiar (las 8 preguntas).
CAMPOS_PERFIL = {
    **dict.fromkeys(["nombre", "titular", "roles_objetivo", "habilidades", "experiencia", "anos_experiencia",
                     "idiomas", "ubicacion", "industrias"]),
    "preferencias": {"dias", "modalidad", "dias_remotos", "salario_minimo_dop", "salario_flexible_startups"},
    "enlaces": {"portafolio", "github", "linkedin"},
    "ia": {"proveedor", "modelo"},
}


def crear_app(demo: bool = False, busqueda: Busqueda | None = None) -> Flask:
    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    app.json.ensure_ascii = False
    app.config["DEMO"] = demo
    busqueda = busqueda or Busqueda()

    @app.before_request
    def solo_local():
        # Solo esta computadora, y solo con el nombre localhost (evita "DNS rebinding").
        if not ipaddress.ip_address(request.remote_addr or "0.0.0.0").is_loopback:
            abort(403)
        if (request.host or "").rsplit(":", 1)[0] not in HOSTS_PERMITIDOS:
            abort(403)
        # Los cambios solo se aceptan como JSON: otra página web no puede enviarlos sin permiso del navegador.
        if request.method == "POST" and not request.is_json:
            abort(415)

    @app.errorhandler(DatosError)
    def datos_error(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(ia.IAError)
    def ia_error(exc):
        return jsonify(error=str(exc)), 502

    @app.get("/")
    def inicio():
        return render_template("index.html", nombre=NOMBRE, estados=ESTADOS, industrias=INDUSTRIAS)

    @app.get("/api/resumen")
    def api_resumen():
        with abrir_store(False) as s:
            r = s.resumen()
            nov = s.novedades()
        return jsonify(resumen=r, novedades=nov, perfil_existe=pf.existe() or app.config.get("DEMO", False), estados=ESTADOS,
                       con_documentos=sorted(ESTADOS_CON_DOCUMENTOS))

    @app.get("/api/vacantes")
    def api_vacantes():
        min_aj = request.args.get("min", type=int)
        with abrir_store(False) as s:
            vacs = s.vacantes(request.args.get("estado") or None, min_aj, request.args.get("empresa") or None)
        for v in vacs:
            v.pop("descripcion", None)
        return jsonify(vacs)

    @app.get("/api/vacantes/<int:vid>")
    def api_vacante(vid: int):
        with abrir_store(False) as s:
            v = s.get_vacante(vid)
            if not v:
                abort(404)
            emp = s.get_empresa(v["empresa_id"]) if v["empresa_id"] else None
            v["historial"] = s.historial(vid)
        v["mensaje"] = redaccion.leer(v["mensaje_path"])
        v["carta"] = redaccion.leer(v["carta_path"])
        v["contactos"] = contactos(emp) if emp else []
        v["empresa"] = emp
        return jsonify(v)

    @app.post("/api/vacantes/<int:vid>/estado")
    def api_estado(vid: int):
        body = request.get_json()
        with abrir_store() as s:
            return jsonify(s.cambiar_estado(vid, body.get("estado", ""), body.get("nota", "")))

    @app.post("/api/vacantes/<int:vid>/nota")
    def api_nota(vid: int):
        with abrir_store() as s:
            return jsonify(s.set_nota(vid, request.get_json().get("nota", "")))

    @app.post("/api/vacantes/<int:vid>/seguimiento")
    def api_seguimiento(vid: int):
        with abrir_store() as s:
            return jsonify(s.set_seguimiento(vid, request.get_json().get("fecha", "")))

    @app.post("/api/vacantes/<int:vid>/generar")
    def api_generar(vid: int):
        body = request.get_json()
        tipos = (body["tipo"],) if body.get("tipo") in redaccion.TIPOS else redaccion.TIPOS
        perfil = pf.cargar()
        with abrir_store() as s:
            paths = redaccion.generar(s, perfil, vid, tipos, body.get("idioma") or None)
        origen = ia.proveedor(perfil) if ia.disponible(perfil) else "plantilla"
        return jsonify({t: redaccion.leer(p) for t, p in paths.items()} | {"origen": origen})

    @app.errorhandler(pf.PerfilError)
    def perfil_error(exc):
        return jsonify(error=str(exc)), 400

    @app.get("/api/perfil")
    def api_perfil():
        return jsonify(perfil=pf.cargar(), existe=pf.existe())

    @app.post("/api/perfil")
    def api_guardar_perfil():
        body = request.get_json() or {}
        data = pf.cargar()
        for clave, sub in CAMPOS_PERFIL.items():
            if clave not in body:
                continue
            if sub is None:
                data[clave] = body[clave]
            elif isinstance(body[clave], dict):
                data[clave].update({k: v for k, v in body[clave].items() if k in sub})
        pf.guardar(data)
        return jsonify(perfil=pf.cargar(), existe=True)

    @app.get("/api/buscar")
    def api_estado_busqueda():
        return jsonify(busqueda.estado())

    @app.post("/api/buscar")
    def api_buscar():
        if app.config.get("DEMO"):
            return jsonify(error="La búsqueda no está disponible con los datos de demostración."), 400
        if not pf.existe():
            return jsonify(error="Primero guarda tu perfil."), 400
        try:
            busqueda.iniciar()
        except BusquedaEnCurso as exc:
            return jsonify(error=str(exc)), 409
        return jsonify(busqueda.estado())

    @app.get("/api/empresas")
    def api_empresas():
        with abrir_store(False) as s:
            emps = s.empresas()
            conteo = {r["empresa_id"]: r["n"] for r in s.conn.execute(
                "SELECT empresa_id, COUNT(*) n FROM vacantes WHERE activa = 1 GROUP BY empresa_id")}
        for e in emps:
            e["contactos"] = contactos(e)
            e["vacantes_activas"] = conteo.get(e["id"], 0)
        return jsonify(emps)

    @app.get("/api/excel")
    def api_excel():
        with abrir_store(False) as s:
            try:
                path = exportar(s)
            except PermissionError:
                path = config.xlsx_path()
        return send_file(path, as_attachment=True, download_name="oportunidades.xlsx")

    return app


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Tablero local de Oportunidades RD")
    ap.add_argument("--puerto", type=int, default=PUERTO)
    ap.add_argument("--no-abrir", action="store_true", help="no abrir el navegador")
    ap.add_argument("--demo", action="store_true", help="usar los datos de demostración (scripts/demo.py)")
    args = ap.parse_args(argv)
    if args.demo:
        import os
        os.environ[config.DATA_ENV] = str(ROOT / "data" / "demo")
    url = f"http://localhost:{args.puerto}"
    print(f"{NOMBRE}: {url}  (Ctrl+C para cerrar)")
    if not args.no_abrir:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    crear_app(args.demo).run(host=HOST, port=args.puerto, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
