#!/usr/bin/env python3
"""Tu perfil (se guarda en ~/.config/oportunidades-rd/profile.yaml, nunca en el repo).

Uso:
    python scripts/perfil.py show              # ver el perfil (y qué falta)
    python scripts/perfil.py path              # dónde está el archivo
    python scripts/perfil.py set habilidades "Python; SQL; Power Automate"
    python scripts/perfil.py set preferencias.salario_minimo_dop 100000
    python scripts/perfil.py set ia.proveedor claude      # agente | claude | openai | ninguno
    python scripts/perfil.py importar mi-perfil.yaml      # cargar un YAML completo
    python scripts/perfil.py ejemplo                      # copiar profile.example.yaml como punto de partida
    python scripts/perfil.py sugerir                      # habilidades y roles sugeridos (sin IA, mapa local)
    python scripts/perfil.py sugerencias --archivo s.json # guardar las sugerencias refinadas por el agente
    python scripts/perfil.py sugerencias --borrar         # quitarlas

Formato de s.json: {"habilidades": ["..."], "roles": [{"rol": "...", "razon": "una línea"}]}
"""
from __future__ import annotations

import argparse
import json

from _comun import ROOT, imprimir_json, salir_error

from oportunidades import config, perfil as pf, sugerencias as sg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sub.add_parser("path")
    s = sub.add_parser("set")
    s.add_argument("clave")
    s.add_argument("valor")
    i = sub.add_parser("importar")
    i.add_argument("archivo")
    sub.add_parser("ejemplo")
    sub.add_parser("sugerir")
    s = sub.add_parser("sugerencias")
    grupo = s.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--archivo")
    grupo.add_argument("--borrar", action="store_true")
    args = ap.parse_args(argv)
    try:
        path = config.profile_path()
        if args.cmd == "path":
            print(path)
        elif args.cmd == "show":
            if not path.exists():
                print(f"Todavía no hay perfil ({path}). El agente te hará unas preguntas para crearlo.")
                return 2
            data = pf.cargar()
            imprimir_json(data)
            falta = pf.faltantes(data)
            if falta:
                print("\nFALTA: " + ", ".join(falta))
        elif args.cmd == "set":
            data = pf.set_campo(pf.cargar(), args.clave, args.valor)
            pf.guardar(data)
            print(f"Guardado {args.clave} en {path}")
        elif args.cmd == "importar":
            pf.guardar(pf.importar(args.archivo, pf.cargar()))
            print(f"Perfil importado en {path}")
        elif args.cmd == "ejemplo":
            if path.exists():
                salir_error(f"Ya existe un perfil en {path}; no lo sobrescribo.")
            pf.guardar(pf.importar(ROOT / "profile.example.yaml"))
            print(f"Copiado el perfil de ejemplo a {path}. Cámbialo con 'set' o edita el archivo.")
        elif args.cmd == "sugerir":
            imprimir_json(sg.sugerir(pf.cargar()))
        elif args.cmd == "sugerencias":
            data = pf.cargar()
            if args.borrar:
                data["sugerencias"] = {}
            else:
                with open(args.archivo, encoding="utf-8") as fh:
                    data["sugerencias"] = json.load(fh)
            pf.guardar(data)
            s = pf.cargar()["sugerencias"]
            print(f"Sugerencias del agente: {len(s['habilidades'])} habilidades y {len(s['roles'])} roles en {path}")
    except (pf.PerfilError, config.ConfigError, OSError, json.JSONDecodeError) as exc:
        salir_error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
