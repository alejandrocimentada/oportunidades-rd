#!/usr/bin/env python3
"""Empresas donde podrías trabajar (las sugiere el agente; tú también puedes agregarlas).

Uso:
    python scripts/empresas.py add --nombre "Empresa X" --industria banca --web https://x.com.do \
        --empleos https://x.com.do/empleos --por-que "Tiene un equipo de datos nuevo..." --interes 80 \
        --rol "Gerente de Innovación" --rol "Head of Data"
    python scripts/empresas.py list [--json]
    python scripts/empresas.py show "Empresa X"         # incluye roles a contactar y búsquedas de LinkedIn
    python scripts/empresas.py update "Empresa X" --interes 90 --empleos https://...
    python scripts/empresas.py remove "Empresa X"
    python scripts/empresas.py industrias

Solo se guardan ROLES de contacto (cargos), nunca nombres, correos ni teléfonos de personas.
"""
from __future__ import annotations

import argparse

from _comun import imprimir_json, salir_error

from oportunidades.contactos import contactos, roles_sugeridos
from oportunidades.db import INDUSTRIAS, DatosError
from oportunidades.servicio import abrir_store


def _args_empresa(p, requerido: bool):
    p.add_argument("--industria", choices=INDUSTRIAS, default="otra" if requerido else None)
    p.add_argument("--web", default="" if requerido else None)
    p.add_argument("--empleos", default="" if requerido else None, help="página pública de empleos")
    p.add_argument("--por-que", default="" if requerido else None)
    p.add_argument("--interes", type=int, default=50 if requerido else None, help="0-100")
    p.add_argument("--rol", action="append", help="cargo a contactar (repetible, máx. 5)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--nombre", required=True)
    _args_empresa(a, True)
    l = sub.add_parser("list")
    l.add_argument("--json", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("empresa")
    u = sub.add_parser("update")
    u.add_argument("empresa")
    _args_empresa(u, False)
    r = sub.add_parser("remove")
    r.add_argument("empresa")
    sub.add_parser("industrias")
    args = ap.parse_args(argv)

    with abrir_store() as store:
        try:
            if args.cmd == "industrias":
                print("\n".join(INDUSTRIAS))
            elif args.cmd == "add":
                roles = args.rol or roles_sugeridos(args.industria)
                e = store.add_empresa(args.nombre, args.industria, args.web, args.empleos, args.por_que,
                                      args.interes, roles)
                print(f"Guardada: [{e['id']}] {e['nombre']} · {e['industria']} · interés {e['interes']}"
                      f" · rastreo: {e['estado_rastreo']}")
            elif args.cmd == "list":
                emps = store.empresas()
                if args.json:
                    imprimir_json(emps)
                else:
                    for e in emps:
                        print(f"[{e['id']:>3}] {e['interes']:>3}  {e['nombre']:<32} {e['industria']:<24} "
                              f"{e['estado_rastreo']:<20} {e['url_empleos'] or '(sin página de empleos)'}")
                    if not emps:
                        print("No hay empresas todavía.")
            else:
                e = store.get_empresa(args.empresa)
                if not e:
                    salir_error(f"No encuentro la empresa «{args.empresa}».")
                if args.cmd == "show":
                    imprimir_json(dict(e, contactos=contactos(e)))
                elif args.cmd == "update":
                    e = store.update_empresa(e["id"], industria=args.industria, sitio_web=args.web,
                                             url_empleos=args.empleos, por_que=args.por_que,
                                             interes=args.interes, roles=args.rol)
                    print(f"Actualizada: [{e['id']}] {e['nombre']}")
                elif args.cmd == "remove":
                    store.remove_empresa(e["id"])
                    print(f"Eliminada: {e['nombre']} (sus vacantes se conservan)")
        except DatosError as exc:
            salir_error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
