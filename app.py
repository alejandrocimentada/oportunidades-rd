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
from oportunidades.db import ESTADOS, ESTADOS_CON_DOCUMENTOS, DatosError  # noqa: E402
from oportunidades.exportar import exportar  # noqa: E402
from oportunidades.servicio import abrir_store  # noqa: E402

HOST, PUERTO = "127.0.0.1", 8765
HOSTS_PERMITIDOS = {"localhost", "127.0.0.1"}


def crear_app(demo: bool = False) -> Flask:
    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    app.json.ensure_ascii = False
    app.config["DEMO"] = demo

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
        return render_template("index.html", nombre=NOMBRE, estados=ESTADOS)

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
