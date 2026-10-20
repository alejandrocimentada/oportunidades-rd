#!/usr/bin/env python3
"""Vacantes abiertas que el rastreador encontró en las páginas de empleo de tus empresas.

Es una comprobación secundaria («¿hay vacantes o no?»): el seguimiento y los textos se hacen por
empresa (scripts/empresas.py).

Uso:
    python scripts/vacantes.py list [--empresa "X"] [--activas] [--json]
    python scripts/vacantes.py show 12
"""
from __future__ import annotations

import argparse

from _comun import imprimir_json, salir_error

from oportunidades.servicio import abrir_store


def _linea(v: dict) -> str:
    activa = "" if v["activa"] else "  (ya no aparece)"
    return f"[{v['id']:>3}] {v['empresa_nombre'][:28]:<28} {v['titulo'][:60]:<60} {v['ubicacion'][:24]}{activa}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list")
    l.add_argument("--empresa")
    l.add_argument("--activas", action="store_true", help="solo las que siguen publicadas")
    l.add_argument("--json", action="store_true")
    sub.add_parser("show").add_argument("id", type=int)
    args = ap.parse_args(argv)

    with abrir_store(exportar_al_cambiar=False) as store:
        if args.cmd == "list":
            vacs = store.vacantes(args.empresa, incluir_inactivas=not args.activas)
            if args.json:
                imprimir_json(vacs)
            else:
                print("\n".join(_linea(v) for v in vacs) or "No hay vacantes con ese filtro.")
        else:
            v = store.get_vacante(args.id)
            if not v:
                salir_error(f"No existe la vacante {args.id}.")
            imprimir_json(v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
