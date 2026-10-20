#!/usr/bin/env python3
"""Empresas en la República Dominicana donde podrías trabajar, y su seguimiento.

El agente las descubre (búsqueda web) y las guarda desde un archivo JSON; tú también puedes hacerlo.

Uso:
    python scripts/empresas.py contexto --json          # perfil + empresas ya guardadas (para el agente)
    python scripts/empresas.py guardar --archivo empresa.json   # una empresa o una lista; repetir = actualizar
    python scripts/empresas.py list [--estado "Me interesa"] [--json]
    python scripts/empresas.py show "Empresa X"         # todo: equipos, roles, evidencia, cómo postular, contactos
    python scripts/empresas.py update "Empresa X" --empleos https://... --portal-rd https://... --talento https://...
    python scripts/empresas.py remove "Empresa X"

    # Seguimiento
    python scripts/empresas.py estado "Empresa X" "Me interesa" [--nota "..."]
        estados: Descubierta, Me interesa, Investigando, Contacté, Aplicado, Entrevista, Oferta, Descartada
    python scripts/empresas.py nota "Empresa X" "Hablé con Talent Acquisition"
    python scripts/empresas.py seguimiento "Empresa X" 2026-11-03
    python scripts/empresas.py historial "Empresa X"

    # Mensaje y carta (solo «Me interesa» o más avanzadas). Se guardan como archivos; nunca se envían.
    python scripts/empresas.py generar "Empresa X" [--tipo mensaje|carta] [--idioma es|en] [--rol "BI Analyst"]
    python scripts/empresas.py guardar-texto "Empresa X" --tipo carta --archivo carta.md   # texto del agente

    python scripts/empresas.py tipos | industrias

Formato del JSON (ver SKILL.md): nombre, tipo, industria, sitio_web, presencia_rd, fuentes_presencia
[{titulo, url}] (al menos una: sin fuente no se agrega), equipos [..], roles [{rol, razon}],
evidencia [{texto, url}], razones [3], alertas [..], url_empleos, portal_rd, talento, linkedin_empresa,
roles_contacto [2-3 cargos]. Solo cargos: nunca nombres, correos ni teléfonos de personas.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _comun import imprimir_json, salir_error

from oportunidades import ia, perfil as pf, redaccion
from oportunidades.contactos import contactos, url_linkedin_empresa
from oportunidades.db import ESTADOS, INDUSTRIAS, TIPOS_EMPRESA, DatosError
from oportunidades.servicio import abrir_store


def _linea(e: dict) -> str:
    return (f"[{e['id']:>3}] {e['estado']:<12} {e['nombre'][:34]:<34} {e['tipo'][:22]:<22} "
            f"{e['industria'][:20]:<20} vacantes: {e['vacantes']}")


def _completa(e: dict) -> dict:
    return dict(e, contactos=contactos(e), linkedin=url_linkedin_empresa(e),
                mensaje=redaccion.leer(e["mensaje_path"]), carta=redaccion.leer(e["carta_path"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("contexto").add_argument("--json", action="store_true")
    g = sub.add_parser("guardar")
    g.add_argument("--archivo", required=True, help="JSON con una empresa o una lista de empresas")
    l = sub.add_parser("list")
    l.add_argument("--estado", choices=ESTADOS)
    l.add_argument("--json", action="store_true")
    for nombre in ("show", "remove", "historial"):
        sub.add_parser(nombre).add_argument("empresa")
    u = sub.add_parser("update")
    u.add_argument("empresa")
    u.add_argument("--tipo", choices=TIPOS_EMPRESA)
    u.add_argument("--industria", choices=INDUSTRIAS)
    u.add_argument("--web")
    u.add_argument("--empleos", help="página pública de empleos que se rastrea (no un portal)")
    u.add_argument("--portal-rd", help="portal de empleos filtrado a RD (solo un enlace para ti)")
    u.add_argument("--talento", help="banco de talento o postulación general")
    u.add_argument("--linkedin", help="página de LinkedIn de la empresa (linkedin.com/company/…)")
    u.add_argument("--rol-contacto", action="append", help="cargo a contactar (repetible, máx. 5)")
    e = sub.add_parser("estado")
    e.add_argument("empresa")
    e.add_argument("estado", choices=ESTADOS)
    e.add_argument("--nota", default="")
    n = sub.add_parser("nota")
    n.add_argument("empresa")
    n.add_argument("texto")
    s = sub.add_parser("seguimiento")
    s.add_argument("empresa")
    s.add_argument("fecha", help="AAAA-MM-DD, o '' para quitarlo")
    gen = sub.add_parser("generar")
    gen.add_argument("empresa")
    gen.add_argument("--tipo", choices=redaccion.TIPOS)
    gen.add_argument("--idioma", choices=["es", "en"])
    gen.add_argument("--rol", help="rol probable en el que centrar el texto (por defecto, el primero)")
    gt = sub.add_parser("guardar-texto")
    gt.add_argument("empresa")
    gt.add_argument("--tipo", choices=redaccion.TIPOS, required=True)
    gt.add_argument("--archivo", required=True)
    sub.add_parser("tipos")
    sub.add_parser("industrias")
    args = ap.parse_args(argv)

    with abrir_store() as store:
        try:
            if args.cmd == "tipos":
                print("\n".join(TIPOS_EMPRESA))
                return 0
            if args.cmd == "industrias":
                print("\n".join(INDUSTRIAS))
                return 0
            if args.cmd == "contexto":
                data = {"perfil": ia.perfil_para_ia(pf.cargar()), "perfil_existe": pf.existe(),
                        "empresas_guardadas": [{k: x[k] for k in ("id", "nombre", "estado", "tipo", "industria")}
                                               for x in store.empresas()]}
                imprimir_json(data) if args.json else print(json.dumps(data, ensure_ascii=False, indent=2))
                return 0
            if args.cmd == "guardar":
                data = json.loads(Path(args.archivo).read_text(encoding="utf-8"))
                errores = 0
                for item in data if isinstance(data, list) else [data]:
                    try:
                        emp, nueva = store.guardar_empresa(item)
                        print(("Agregada" if nueva else "Actualizada") + f": {_linea(emp)}")
                    except DatosError as exc:
                        errores += 1
                        print(f"NO guardada: {exc}")
                return 1 if errores else 0
            if args.cmd == "list":
                emps = store.empresas(args.estado)
                if args.json:
                    imprimir_json(emps)
                else:
                    print("\n".join(_linea(x) for x in emps) or "No hay empresas todavía.")
                return 0

            emp = store.get_empresa(args.empresa)
            if not emp:
                salir_error(f"No encuentro la empresa «{args.empresa}».")
            if args.cmd == "show":
                imprimir_json(_completa(emp))
            elif args.cmd == "remove":
                store.remove_empresa(emp["id"])
                print(f"Eliminada: {emp['nombre']} (y sus vacantes)")
            elif args.cmd == "historial":
                for h in store.historial(emp["id"]):
                    print(f"{h['fecha'].replace('T', ' ')}  {h['de_estado'] or '·':<12} → {h['a_estado']:<12} {h['nota']}")
            elif args.cmd == "update":
                campos = {"tipo": args.tipo, "industria": args.industria, "sitio_web": args.web,
                          "url_empleos": args.empleos, "portal_rd": args.portal_rd, "talento": args.talento,
                          "linkedin_empresa": args.linkedin, "roles_contacto": args.rol_contacto}
                print(f"Actualizada: {_linea(store.update_empresa(emp['id'], **campos))}")
            elif args.cmd == "estado":
                x = store.cambiar_estado(emp["id"], args.estado, args.nota)
                print(_linea(x) + (f"   seguimiento: {x['seguimiento']}" if x["seguimiento"] else ""))
            elif args.cmd == "nota":
                store.set_nota(emp["id"], args.texto)
                print("Nota guardada.")
            elif args.cmd == "seguimiento":
                print(f"Seguimiento: {store.set_seguimiento(emp['id'], args.fecha)['seguimiento'] or '(ninguno)'}")
            elif args.cmd == "generar":
                tipos = (args.tipo,) if args.tipo else redaccion.TIPOS
                for tipo, path in redaccion.generar(store, pf.cargar(), emp["id"], tipos, args.idioma, args.rol).items():
                    print(f"{tipo}: {path}")
                print("Revisa y edita los textos antes de enviarlos. Nada se envía solo.")
            elif args.cmd == "guardar-texto":
                path = redaccion.guardar_texto(store, emp, args.tipo, Path(args.archivo).read_text(encoding="utf-8"))
                print(f"{args.tipo}: {path}")
        except (DatosError, ia.IAError) as exc:
            salir_error(str(exc))
        except (OSError, ValueError) as exc:
            salir_error(f"No se pudo leer el archivo: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
