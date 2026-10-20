#!/usr/bin/env python3
"""Construye static/esco.json (índice local de habilidades y ocupaciones de ESCO) desde los CSV oficiales.

Uso:
    python scripts/construir_esco.py --origen ESCO_es.zip --origen ESCO_en.zip
    python scripts/construir_esco.py --origen data/esco/es --origen data/esco/en --version v1.2.1

Los CSV se descargan en https://esco.ec.europa.eu/en/use-esco/download (versión «ESCO dataset v1.2.1»,
contenido «classification», idiomas español e inglés, formato CSV; ESCO envía el enlace por correo).
Se usan: skills_es.csv, skills_en.csv, occupations_es.csv, occupations_en.csv y occupationSkillRelations*.csv.

ESCO es de la Comisión Europea, con licencia CC BY 4.0 (ver README, «Créditos»). Este índice es una versión
reducida: etiqueta en español e inglés, algunos sinónimos y, por ocupación, sus habilidades esenciales.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

from _comun import ROOT, salir_error

from oportunidades.sugerencias import normalizar

DESTINO = ROOT / "static" / "esco.json"
# Límites para que el índice pese poco (los sinónimos eran casi la mitad del archivo).
# Sinónimos cortos (nombres de herramientas, siglas: «MS Excel», «SAP») son baratos y son lo que la gente escribe;
# de los largos (frases) se guardan pocos.
MAX_SINONIMOS_CORTOS, LARGO_CORTO = {"es": 4, "en": 6}, 15
MAX_SINONIMOS = {"es": 2, "en": 1}         # largos, por habilidad
MAX_LARGO_SINONIMO = 40                   # los larguísimos no ayudan a buscar
MAX_ALTERNATIVAS_OCUPACION = {"es": 4, "en": 1}  # en español incluyen las formas en femenino («contadora»)
MAX_HABILIDADES_OCUPACION = 15
# ESCO está en español de España. Palabras de RD (normalizadas, sin tildes) → la de ESCO; el buscador y el puesto
# prueban las dos, así que esto solo añade resultados.
EQUIVALENCIAS_RD = {"contador": "contable", "contadora": "contable", "mesero": "camarero", "mesera": "camarera",
                    "chofer": "conductor", "plomero": "fontanero", "mercadeo": "marketing", "computadora": "ordenador",
                    "computador": "ordenador", "computacion": "informatica", "celular": "movil"}
# Condiciones de ESCO: su frase exacta, y decir que el índice es una versión adaptada.
FRASE_ESCO = "This service uses the ESCO classification of the European Commission."
ATRIBUCION = (f"{FRASE_ESCO} Versión adaptada por Oportunidades RD: índice reducido (etiquetas en español e inglés, "
              "algunos sinónimos y habilidades esenciales por ocupación). Licencia CC BY 4.0.")
ARCHIVOS = {"skills_es": r"skills_es\.csv", "skills_en": r"skills_en\.csv", "occupations_es": r"occupations_es\.csv",
            "occupations_en": r"occupations_en\.csv", "relaciones": r"occupationskillrelations(_[a-z]+)?\.csv"}


def _leer_csv(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto)))


def encontrar(origenes: list[Path]) -> dict[str, list[dict]]:
    """Busca los CSV en zips o carpetas (en cualquier subcarpeta) y los lee."""
    hallados: dict[str, list[dict]] = {}
    for origen in origenes:
        if origen.is_dir():
            for p in origen.rglob("*.csv"):
                _guardar(hallados, p.name, lambda p=p: p.read_text(encoding="utf-8-sig"))
        elif zipfile.is_zipfile(origen):
            with zipfile.ZipFile(origen) as z:
                for nombre in z.namelist():
                    _guardar(hallados, Path(nombre).name, lambda n=nombre, z=z: z.read(n).decode("utf-8-sig"))
        else:
            raise FileNotFoundError(f"No es una carpeta ni un .zip: {origen}")
    faltan = [k for k in ARCHIVOS if k not in hallados]
    if faltan:
        raise FileNotFoundError("Faltan archivos de ESCO: " + ", ".join(ARCHIVOS[k].replace("\\", "") for k in faltan)
                                + ". Descarga la clasificación en español e inglés, en CSV.")
    return hallados


def _guardar(hallados: dict, nombre: str, leer) -> None:
    for clave, patron in ARCHIVOS.items():
        if clave not in hallados and re.fullmatch(patron, nombre, flags=re.IGNORECASE):
            hallados[clave] = _leer_csv(leer())


def _vigentes(filas: list[dict]) -> dict[str, dict]:
    return {f["conceptUri"]: f for f in filas if f.get("conceptUri") and (f.get("status") or "released") == "released"
            and (f.get("preferredLabel") or "").strip()}


def _alternativas(fila: dict | None) -> list[str]:
    return [x.strip() for x in re.split(r"[\n|]", (fila or {}).get("altLabels") or "") if x.strip()]


def _version(origenes: list[Path], version: str | None) -> str:
    """La versión de ESCO: la indicada, o la que aparece en la ruta («ESCO dataset - v1.2.1 - …»)."""
    if version:
        return version if version.startswith("v") else f"v{version}"
    for o in origenes:
        m = re.search(r"v\d+\.\d+(\.\d+)?", str(o.resolve()))
        if m:
            return m.group(0)
    raise FileNotFoundError("No sé qué versión de ESCO es: indícala con --version (por ejemplo, --version v1.2.1).")


def construir(origenes: list[Path], destino: Path = DESTINO, version: str | None = None) -> dict:
    version = _version(origenes, version)
    datos = encontrar(origenes)
    hab_es, hab_en = _vigentes(datos["skills_es"]), _vigentes(datos["skills_en"])
    ocu_es, ocu_en = _vigentes(datos["occupations_es"]), _vigentes(datos["occupations_en"])

    esenciales: dict[str, list[str]] = {}
    uso = Counter()
    for r in datos["relaciones"]:
        o, h, tipo = r.get("occupationUri"), r.get("skillUri"), (r.get("relationType") or "").lower()
        if o in ocu_es and h in hab_es:
            uso[h] += 2 if tipo == "essential" else 1
            if tipo == "essential":
                esenciales.setdefault(o, []).append(h)

    # Las habilidades más usadas por las ocupaciones van primero: así desempatan el buscador y los sinónimos.
    uris = sorted(hab_es, key=lambda u: (-uso[u], hab_es[u]["preferredLabel"].strip().lower(), u))
    indice = {u: i for i, u in enumerate(uris)}
    habilidades = []
    for u in uris:
        es = hab_es[u]["preferredLabel"].strip()
        en = (hab_en.get(u) or {}).get("preferredLabel", "").strip()
        vistos, sinonimos = {normalizar(es), normalizar(en)}, []
        for idioma, fila in (("es", hab_es[u]), ("en", hab_en.get(u))):
            cortos = largos = 0
            for s in _alternativas(fila):
                n, corto = normalizar(s), len(s) <= LARGO_CORTO
                cabe = cortos < MAX_SINONIMOS_CORTOS[idioma] if corto else largos < MAX_SINONIMOS[idioma]
                if cabe and len(s) <= MAX_LARGO_SINONIMO and n and n not in vistos:
                    vistos.add(n)
                    sinonimos.append(s)
                    cortos, largos = cortos + corto, largos + (not corto)
        habilidades.append([es, en, sinonimos])

    ocupaciones = []
    for u in sorted(ocu_es, key=lambda u: ocu_es[u]["preferredLabel"].strip().lower()):
        es = ocu_es[u]["preferredLabel"].strip()
        en = (ocu_en.get(u) or {}).get("preferredLabel", "").strip()
        vistos, alternativas = {normalizar(es), normalizar(en)}, []
        for idioma, fila in (("es", ocu_es[u]), ("en", ocu_en.get(u))):
            nuevas = [a for a in _alternativas(fila) if normalizar(a) not in vistos][:MAX_ALTERNATIVAS_OCUPACION[idioma]]
            vistos.update(normalizar(a) for a in nuevas)
            alternativas += nuevas
        hs = sorted({indice[h] for h in esenciales.get(u, [])})[:MAX_HABILIDADES_OCUPACION]
        ocupaciones.append([es, en, alternativas, hs])

    salida = {"fuente": f"ESCO {version}", "licencia": "CC BY 4.0", "adaptado": True, "atribucion": ATRIBUCION,
              "equivalencias": EQUIVALENCIAS_RD, "h": habilidades, "o": ocupaciones}
    texto = json.dumps(salida, ensure_ascii=False, separators=(",", ":"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8", newline="\n")
    crudo = len(texto.encode("utf-8"))
    return {"destino": str(destino), "fuente": salida["fuente"], "habilidades": len(habilidades), "ocupaciones": len(ocupaciones),
            "bytes": crudo, "gzip": len(gzip.compress(texto.encode("utf-8"), 9))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Índice local de ESCO para el buscador de habilidades")
    ap.add_argument("--origen", type=Path, action="append", required=True, help="zip o carpeta con los CSV (repetible)")
    ap.add_argument("--destino", type=Path, default=DESTINO)
    ap.add_argument("--version", help="versión de ESCO (p. ej. v1.2.1) si no aparece en la ruta")
    args = ap.parse_args(argv)
    try:
        r = construir(args.origen, args.destino, args.version)
    except (FileNotFoundError, KeyError, csv.Error) as exc:
        salir_error(str(exc))
    print(f"{r['fuente']}: {r['habilidades']} habilidades y {r['ocupaciones']} ocupaciones → {r['destino']}")
    print(f"Tamaño: {r['bytes'] / 1e6:.2f} MB ({r['gzip'] / 1e6:.2f} MB comprimido con gzip)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
