#!/usr/bin/env python3
"""Rastrea las páginas públicas de empleo de tus empresas y muestra las novedades.

Educado: respeta robots.txt, 1 petición cada 3 s por sitio, caché de 24 h, User-Agent claro.
Nunca entra a LinkedIn, Computrabajo, Indeed ni otros portales (para esos: scripts/pegar.py).

Uso:
    python scripts/rastrear.py                    # todas las empresas con página de empleos
    python scripts/rastrear.py --empresa "Empresa X" --empresa 7
    python scripts/rastrear.py --sin-detalles     # no abre la página de cada vacante
    python scripts/rastrear.py --sin-cache        # ignora la caché de 24 h
    python scripts/rastrear.py --novedades        # solo muestra lo nuevo del último rastreo
"""
from __future__ import annotations

import argparse

from _comun import imprimir_json, salir_error

from oportunidades import perfil as pf
from oportunidades.crawler import Fetcher
from oportunidades.servicio import abrir_store, rastrear


def mostrar_novedades(nov: dict) -> None:
    c = nov["corrida"]
    if not c:
        print("Todavía no hay rastreos.")
        return
    print(f"\n=== NOVEDADES (rastreo del {c['inicio'].replace('T', ' ')}) ===")
    if nov["nuevas"]:
        print(f"\n{len(nov['nuevas'])} vacantes nuevas:")
        for v in nov["nuevas"]:
            print(f"  [{v['id']}] {v['ajuste'] if v['ajuste'] is not None else '–':>3}  {v['empresa_nombre']} · "
                  f"{v['titulo']}  {v['url']}")
    else:
        print("\nNo hay vacantes nuevas desde el rastreo anterior.")
    if nov["ya_no_aparecen"]:
        print(f"\n{len(nov['ya_no_aparecen'])} ya no aparecen en la página:")
        for v in nov["ya_no_aparecen"]:
            print(f"  [{v['id']}] {v['empresa_nombre']} · {v['titulo']} ({v['estado']})")
    if nov["manuales"]:
        print("\nRevisa tú en el navegador:")
        for m in nov["manuales"]:
            print(f"  - {m['empresa']} ({m['estado']}): {m['motivo']}\n    {m['enlace']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--empresa", action="append", help="nombre o id (repetible)")
    ap.add_argument("--sin-detalles", action="store_true")
    ap.add_argument("--sin-cache", action="store_true")
    ap.add_argument("--sin-puntuar", action="store_true")
    ap.add_argument("--novedades", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with abrir_store() as store:
        if args.novedades:
            nov = store.novedades()
        else:
            if not pf.existe():
                salir_error("Primero crea tu perfil (python scripts/perfil.py show).")
            nov = rastrear(store, pf.cargar(), Fetcher(usar_cache=not args.sin_cache), solo=args.empresa,
                           detalles=not args.sin_detalles, puntuar_nuevas=not args.sin_puntuar)
        if args.json:
            imprimir_json(nov)
        else:
            mostrar_novedades(nov)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
