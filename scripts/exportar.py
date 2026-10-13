#!/usr/bin/env python3
"""Regenera data/oportunidades.xlsx (Resumen, Empresas, Vacantes, Seguimiento).

Se regenera solo después de cada cambio; este script es para forzarlo.

Uso:
    python scripts/exportar.py
"""
from __future__ import annotations

from _comun import salir_error

from oportunidades.exportar import exportar
from oportunidades.servicio import abrir_store


def main() -> int:
    with abrir_store(exportar_al_cambiar=False) as store:
        try:
            print(f"Excel actualizado: {exportar(store)}")
        except PermissionError:
            salir_error("No se pudo escribir el Excel. ¿Está abierto? Ciérralo y vuelve a intentar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
