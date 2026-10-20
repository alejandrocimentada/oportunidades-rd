#!/usr/bin/env python3
"""Construye static/esco.json (índice local de habilidades y ocupaciones de ESCO) desde los CSV oficiales.

Uso:
    python scripts/construir_esco.py --origen ESCO_es.zip --origen ESCO_en.zip
    python scripts/construir_esco.py --origen data/esco/es --origen data/esco/en --version v1.2.1

Los CSV se descargan en https://esco.ec.europa.eu/en/use-esco/download (versión «ESCO dataset v1.2.1»,
contenido «classification», idiomas español e inglés, formato CSV; ESCO envía el enlace por correo).
Se usan: skills_es.csv, skills_en.csv, occupations_es.csv, occupations_en.csv y occupationSkillRelations*.csv.

ESCO es de la Comisión Europea, con licencia CC BY 4.0 (ver README, «Créditos»). Este índice es una versión
adaptada, al estilo de las habilidades de un perfil profesional (nombres cortos, no frases de tareas):
- conocimientos de ESCO de hasta 4 palabras que usa alguna ocupación, sin sufijos como «(programación informática)»;
- las competencias de ESCO más usadas, reescritas como nombre corto (scripts/habilidades/competencias_esco.json);
- herramientas y métodos que ESCO no tiene, curados a mano y marcados «curada» (scripts/habilidades/curadas.json).
Cada ocupación guarda sus habilidades esenciales que quedaron en la lista; así funcionan las sugerencias.
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
CARPETA = ROOT / "scripts" / "habilidades"
COMPETENCIAS = CARPETA / "competencias_esco.json"  # competencias de ESCO reescritas como nombres cortos
CURADAS = CARPETA / "curadas.json"                 # herramientas y métodos que ESCO no tiene (NO son de ESCO)
# Lista al estilo de un perfil profesional: nombres cortos y reconocibles, no frases de tareas.
MAX_PALABRAS = 4               # conocimientos de ESCO de hasta 4 palabras («contabilidad», «diseño gráfico»)
MIN_OCUPACIONES_COMPETENCIA = 40  # competencias candidatas a reescribir (solo para avisar si falta alguna)
# De ESCO solo un sinónimo corto en español («teneduría de libros»): los otros son ruido para buscar («Java Posse»).
MAX_SINONIMOS, MAX_LARGO_SINONIMO = 1, 25
MAX_ALTERNATIVAS_OCUPACION = {"es": 4, "en": 1}  # en español incluyen las formas en femenino («contadora»)
MAX_HABILIDADES_OCUPACION = 15
# ESCO está en español de España. Palabras de RD (normalizadas, sin tildes) → la de ESCO; el buscador y el puesto
# prueban las dos, así que esto solo añade resultados.
EQUIVALENCIAS_RD = {"contador": "contable", "contadora": "contable", "mesero": "camarero", "mesera": "camarera",
                    "chofer": "conductor", "plomero": "fontanero", "mercadeo": "marketing", "computadora": "ordenador",
                    "computador": "ordenador", "computacion": "informatica", "celular": "movil"}
# Condiciones de ESCO: su frase exacta, y decir que el índice es una versión adaptada.
FRASE_ESCO = "This service uses the ESCO classification of the European Commission."
ATRIBUCION = (f"{FRASE_ESCO} Versión adaptada por Oportunidades RD: usamos un subconjunto de las habilidades de ESCO, "
              "reescribimos algunos nombres como habilidades cortas y añadimos habilidades curadas que no son de ESCO "
              "(marcadas «curada»). Licencia CC BY 4.0.")
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


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _version(origenes: list[Path], version: str | None) -> str:
    """La versión de ESCO: la indicada, o la que aparece en la ruta («ESCO dataset - v1.2.1 - …»)."""
    if version:
        return version if version.startswith("v") else f"v{version}"
    for o in origenes:
        m = re.search(r"v\d+\.\d+(\.\d+)?", str(o.resolve()))
        if m:
            return m.group(0)
    raise FileNotFoundError("No sé qué versión de ESCO es: indícala con --version (por ejemplo, --version v1.2.1).")


def limpiar(etiqueta: str) -> str:
    """Quita el sufijo descriptivo entre paréntesis: «Python (programación informática)» → «Python».
    Las siglas se quedan: «Reglamento general de protección de datos (RGPD)»."""
    m = re.fullmatch(r"(.+?)\s*\(([^()]*)\)", etiqueta.strip())
    if m and (" " in m.group(2) or m.group(2) == m.group(2).lower()):
        return m.group(1).strip()
    return etiqueta.strip()


def _palabras(etiqueta: str) -> int:
    return len(re.sub(r"\([^()]*\)", " ", etiqueta).split())


class _Lista:
    """Habilidades unidas por nombre: la misma en español o en inglés es una sola, con todos sus URI de ESCO."""

    def __init__(self):
        self.todas: list[dict] = []
        self.por_nombre: dict[str, dict] = {}

    def agregar(self, es: str, en: str, sinonimos=(), uris=(), popularidad: int = 0, esco: set | None = None) -> None:
        h = self.por_nombre.get(normalizar(es)) or self.por_nombre.get(normalizar(en))
        if h is None:
            h = {"es": es, "en": en, "sinonimos": [], "uris": set(), "popularidad": 0, "esco": set()}
            self.todas.append(h)
        for s in (es, en, *sinonimos):  # otro nombre de la misma habilidad: queda como sinónimo
            n = normalizar(s)
            if n and n not in {normalizar(x) for x in (h["es"], h["en"], *h["sinonimos"])}:
                h["sinonimos"].append(s)
        h["uris"] |= set(uris)
        h["esco"] |= esco or set()
        h["popularidad"] = max(h["popularidad"], popularidad)
        for s in (es, en):
            self.por_nombre.setdefault(normalizar(s), h)


def construir(origenes: list[Path], destino: Path = DESTINO, version: str | None = None,
              competencias: Path = COMPETENCIAS, curadas: Path = CURADAS) -> dict:
    version = _version(origenes, version)
    datos = encontrar(origenes)
    hab_es, hab_en = _vigentes(datos["skills_es"]), _vigentes(datos["skills_en"])
    ocu_es, ocu_en = _vigentes(datos["occupations_es"]), _vigentes(datos["occupations_en"])
    reescritas = json.loads(competencias.read_text(encoding="utf-8"))["competencias"]
    grupos = json.loads(curadas.read_text(encoding="utf-8"))["grupos"]

    esenciales: dict[str, list[str]] = {}
    usan: dict[str, set[str]] = {}  # habilidad → ocupaciones que la piden (esencial u opcional)
    for r in datos["relaciones"]:
        o, h = r.get("occupationUri"), r.get("skillUri")
        if o in ocu_es and h in hab_es:
            usan.setdefault(h, set()).add(o)
            if (r.get("relationType") or "").lower() == "essential":
                esenciales.setdefault(o, []).append(h)
    nombre_esco = lambda u: {normalizar(limpiar(hab_es[u]["preferredLabel"])),
                             normalizar(limpiar((hab_en.get(u) or {}).get("preferredLabel", "")))}

    # 1) Competencias de ESCO reescritas como nombre corto (gestionar proyectos → Gestión de proyectos).
    # 2) Herramientas, métodos y habilidades blandas curadas, que ESCO no tiene.
    # 3) Conocimientos de ESCO de hasta 4 palabras que usa alguna ocupación, sin el sufijo entre paréntesis.
    # Van en ese orden para que, si coinciden, quede el nombre reescrito o curado (y los enlaces de ESCO).
    lista = _Lista()
    for u, c in reescritas.items():
        if u in hab_es and usan.get(u) and not c.get("quitar"):
            lista.agregar(c["es"], c["en"], uris={u})
    for g in grupos:
        for es, en, *resto in g["habilidades"]:
            lista.agregar(es, en, resto[0] if resto else (), popularidad=g["popularidad"])
    for u, f in hab_es.items():
        es = limpiar(f["preferredLabel"])
        if f.get("skillType") == "knowledge" and usan.get(u) and _palabras(es) <= MAX_PALABRAS:
            en = limpiar((hab_en.get(u) or {}).get("preferredLabel", ""))
            sinonimos = [limpiar(s) for s in _alternativas(f) if len(limpiar(s)) <= MAX_LARGO_SINONIMO][:MAX_SINONIMOS]
            lista.agregar(_mayuscula(es), en, sinonimos, uris={u}, esco=nombre_esco(u))
    faltan = [u for u, f in hab_es.items() if u not in reescritas and f.get("skillType") == "skill/competence"
              and f.get("reuseLevel") in ("transversal", "cross-sector") and len(usan.get(u, ())) >= MIN_OCUPACIONES_COMPETENCIA]

    # Popularidad: cuántas ocupaciones de ESCO la piden; las curadas tienen un valor alto fijo por grupo.
    for h in lista.todas:
        h["popularidad"] = max(h["popularidad"], len(set().union(*(usan[u] for u in h["uris"]))) if h["uris"] else 0)
        h["origen"] = ("curada" if not h["uris"] else "esco" if normalizar(h["es"]) in h["esco"] else "reescrita")
    habilidades = sorted(lista.todas, key=lambda h: (-h["popularidad"], normalizar(h["es"]), h["es"]))
    indice = {u: i for i, h in enumerate(habilidades) for u in h["uris"]}

    ocupaciones = []
    for u in sorted(ocu_es, key=lambda u: ocu_es[u]["preferredLabel"].strip().lower()):
        es = ocu_es[u]["preferredLabel"].strip()
        en = (ocu_en.get(u) or {}).get("preferredLabel", "").strip()
        vistos, alternativas = {normalizar(es), normalizar(en)}, []
        for idioma, fila in (("es", ocu_es[u]), ("en", ocu_en.get(u))):
            nuevas = [a for a in _alternativas(fila) if normalizar(a) not in vistos][:MAX_ALTERNATIVAS_OCUPACION[idioma]]
            vistos.update(normalizar(a) for a in nuevas)
            alternativas += nuevas
        hs = sorted({indice[h] for h in esenciales.get(u, []) if h in indice})[:MAX_HABILIDADES_OCUPACION]
        ocupaciones.append([es, en, alternativas, hs])

    salida = {"fuente": f"ESCO {version}", "licencia": "CC BY 4.0", "adaptado": True, "atribucion": ATRIBUCION,
              "equivalencias": EQUIVALENCIAS_RD,
              "campos_h": ["español", "inglés", "sinónimos", "popularidad (ocupaciones de ESCO)", "origen (esco, reescrita o curada)"],
              "h": [[h["es"], h["en"], h["sinonimos"], h["popularidad"], h["origen"]] for h in habilidades],
              "o": ocupaciones}
    texto = json.dumps(salida, ensure_ascii=False, separators=(",", ":"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8", newline="\n")
    crudo = len(texto.encode("utf-8"))
    return {"destino": str(destino), "fuente": salida["fuente"], "habilidades": len(habilidades), "ocupaciones": len(ocupaciones),
            "origenes": dict(Counter(h["origen"] for h in habilidades)), "competencias_sin_revisar": len(faltan),
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
    print("Origen: " + ", ".join(f"{n} {k}" for k, n in sorted(r["origenes"].items())))
    if r["competencias_sin_revisar"]:
        print(f"Aviso: {r['competencias_sin_revisar']} competencias muy usadas no están en {COMPETENCIAS.name}: revísalas.")
    print(f"Tamaño: {r['bytes'] / 1e6:.2f} MB ({r['gzip'] / 1e6:.2f} MB comprimido con gzip)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
