#!/usr/bin/env python3
"""Vacantes: ver, elegir, cambiar de estado, puntuar y preparar el mensaje y la carta.

Uso:
    python scripts/vacantes.py list [--estado "Nuevo"] [--min 60] [--empresa "X"] [--json]
    python scripts/vacantes.py show 12
    python scripts/vacantes.py estado 12 "Me interesa" [--nota "..."]
        estados: Nuevo, Me interesa, Aplicado, Contacté, Entrevista, Oferta, Rechazado, Descartado
    python scripts/vacantes.py nota 12 "Hablé con RR.HH."
    python scripts/vacantes.py seguimiento 12 2026-10-20
    python scripts/vacantes.py historial 12

    # Puntuar (ajuste 0-100, por qué encaja, alertas, lo que falta)
    python scripts/vacantes.py puntuar 12              # IA del perfil o heurística local
    python scripts/vacantes.py puntuar --todas         # todas las que no tienen puntuación
    python scripts/vacantes.py pendientes --json       # para el agente: vacantes sin puntuar + perfil
    python scripts/vacantes.py guardar-puntuacion 12 --ajuste 78 --encaja "..." --encaja "..." \
        --encaja "..." --alerta "..." --falta "..."    # el agente guarda su propia evaluación

    # Mensaje y carta (solo "Me interesa" o más avanzadas). Se guardan como archivos; nunca se envían.
    python scripts/vacantes.py generar 12 [--tipo mensaje|carta] [--idioma es|en]
    python scripts/vacantes.py guardar-texto 12 --tipo carta --archivo carta.md   # texto escrito por el agente
"""
from __future__ import annotations

import argparse
from pathlib import Path

from _comun import imprimir_json, salir_error

from oportunidades import ia, perfil as pf, redaccion
from oportunidades.db import ESTADOS, DatosError
from oportunidades.servicio import abrir_store, puntuar


def _linea(v: dict) -> str:
    aj = v["ajuste"] if v["ajuste"] is not None else "–"
    activa = "" if v["activa"] else "  (ya no aparece)"
    return f"[{v['id']:>3}] {aj:>3}  {v['estado']:<12} {v['empresa_nombre'][:24]:<24} {v['titulo'][:60]}{activa}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list")
    l.add_argument("--estado", choices=ESTADOS)
    l.add_argument("--min", type=int)
    l.add_argument("--empresa")
    l.add_argument("--json", action="store_true")
    for nombre in ("show", "historial"):
        sub.add_parser(nombre).add_argument("id", type=int)
    e = sub.add_parser("estado")
    e.add_argument("id", type=int)
    e.add_argument("estado", choices=ESTADOS)
    e.add_argument("--nota", default="")
    n = sub.add_parser("nota")
    n.add_argument("id", type=int)
    n.add_argument("texto")
    s = sub.add_parser("seguimiento")
    s.add_argument("id", type=int)
    s.add_argument("fecha", help="AAAA-MM-DD, o '' para quitarlo")
    p = sub.add_parser("puntuar")
    p.add_argument("id", type=int, nargs="?")
    p.add_argument("--todas", action="store_true")
    pe = sub.add_parser("pendientes")
    pe.add_argument("--json", action="store_true")
    pe.add_argument("--incluir-puntuadas", action="store_true")
    g = sub.add_parser("guardar-puntuacion")
    g.add_argument("id", type=int)
    g.add_argument("--ajuste", type=int, required=True)
    g.add_argument("--encaja", action="append", default=[])
    g.add_argument("--alerta", action="append", default=[])
    g.add_argument("--falta", action="append", default=[])
    gen = sub.add_parser("generar")
    gen.add_argument("id", type=int)
    gen.add_argument("--tipo", choices=redaccion.TIPOS)
    gen.add_argument("--idioma", choices=["es", "en"])
    gt = sub.add_parser("guardar-texto")
    gt.add_argument("id", type=int)
    gt.add_argument("--tipo", choices=redaccion.TIPOS, required=True)
    gt.add_argument("--archivo", required=True)
    args = ap.parse_args(argv)

    with abrir_store() as store:
        try:
            if args.cmd == "list":
                vacs = store.vacantes(args.estado, args.min, args.empresa)
                if args.json:
                    imprimir_json(vacs)
                else:
                    print("\n".join(_linea(v) for v in vacs) or "No hay vacantes con ese filtro.")
                return 0
            if args.cmd == "pendientes":
                perfil = pf.cargar()
                vacs = store.vacantes() if args.incluir_puntuadas else [v for v in store.vacantes() if v["ajuste"] is None or v["puntuado_por"] == "heurística"]
                data = {"perfil": ia.perfil_para_ia(perfil),
                        "vacantes": [{k: v[k] for k in ("id", "titulo", "empresa_nombre", "ubicacion", "url",
                                                         "descripcion", "ajuste", "puntuado_por")} for v in vacs]}
                if args.json:
                    imprimir_json(data)
                else:
                    print("\n".join(_linea(v) for v in vacs) or "No hay vacantes pendientes.")
                return 0
            if args.cmd == "puntuar":
                perfil = pf.cargar()
                ids = [v["id"] for v in store.vacantes() if v["ajuste"] is None] if args.todas else [args.id]
                if ids == [None]:
                    salir_error("Indica un id o --todas.")
                for vid in ids:
                    print(_linea(puntuar(store, perfil, vid)))
                return 0

            vac = store.get_vacante(args.id)
            if not vac:
                salir_error(f"No existe la vacante {args.id}.")
            if args.cmd == "show":
                vac["mensaje"] = redaccion.leer(vac["mensaje_path"])
                vac["carta"] = redaccion.leer(vac["carta_path"])
                imprimir_json(vac)
            elif args.cmd == "historial":
                for h in store.historial(args.id):
                    print(f"{h['fecha'].replace('T', ' ')}  {h['de_estado'] or '·':<12} → {h['a_estado']:<12} {h['nota']}")
            elif args.cmd == "estado":
                v = store.cambiar_estado(args.id, args.estado, args.nota)
                print(_linea(v) + (f"   seguimiento: {v['seguimiento']}" if v["seguimiento"] else ""))
            elif args.cmd == "nota":
                store.set_nota(args.id, args.texto)
                print("Nota guardada.")
            elif args.cmd == "seguimiento":
                print(f"Seguimiento: {store.set_seguimiento(args.id, args.fecha)['seguimiento'] or '(ninguno)'}")
            elif args.cmd == "guardar-puntuacion":
                v = store.guardar_puntuacion(args.id, args.ajuste, args.encaja, args.alerta, args.falta, "agente")
                print(_linea(v))
            elif args.cmd == "generar":
                tipos = (args.tipo,) if args.tipo else redaccion.TIPOS
                for tipo, path in redaccion.generar(store, pf.cargar(), args.id, tipos, args.idioma).items():
                    print(f"{tipo}: {path}")
                print("Revisa y edita los textos antes de enviarlos. Nada se envía solo.")
            elif args.cmd == "guardar-texto":
                path = redaccion.guardar_texto(store, vac, args.tipo, Path(args.archivo).read_text(encoding="utf-8"))
                print(f"{args.tipo}: {path}")
        except (DatosError, ia.IAError) as exc:
            salir_error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
