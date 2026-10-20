#!/usr/bin/env python3
"""Agrega una vacante que copiaste de LinkedIn, Computrabajo, Indeed u otro portal, como evidencia de
que una empresa contrata en RD.

Esos portales no se rastrean: tú copias el texto del anuncio y lo pegas aquí.

Uso:
    python scripts/pegar.py --archivo vacante.txt --url https://... --empresa "Empresa X"
    python scripts/pegar.py --empresa "Empresa X" < vacante.txt
    (pega el texto y termina con Ctrl+Z y Enter en Windows, o Ctrl+D en Mac/Linux)

La primera línea del texto se usa como título si no das --titulo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _comun import salir_error

from oportunidades.db import DatosError
from oportunidades.servicio import abrir_store, pegar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archivo", help="archivo de texto con el anuncio (si no, se lee de la entrada)")
    ap.add_argument("--url", default="", help="enlace al anuncio (opcional; no se visita)")
    ap.add_argument("--empresa", default="")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--ubicacion", default="")
    args = ap.parse_args(argv)
    texto = Path(args.archivo).read_text(encoding="utf-8") if args.archivo else sys.stdin.read()
    with abrir_store() as store:
        try:
            vac, nueva = pegar(store, texto, args.url, args.empresa, args.titulo, args.ubicacion)
        except (DatosError, ValueError) as exc:
            salir_error(str(exc))
    print(("Agregada" if nueva else "Ya existía") + f": [{vac['id']}] {vac['titulo']} · {vac['empresa_nombre'] or '(sin empresa)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
