"""Habilidades y roles sugeridos SIN IA, a partir de un mapa local (sugerencias.json).

Entra lo que el usuario eligió y contó en el asistente del perfil: áreas de interés, estudios, último puesto,
experiencia y habilidades. Sale una lista ordenada de habilidades y de roles, cada rol con un «por qué».

- Un área cuenta si la eligió (peso 3) o si sus palabras aparecen en su puesto (3), sus estudios (2) u otro
  texto (1). Las áreas se ordenan por esos puntos.
- Los roles y habilidades se reparten POR TURNOS entre las áreas fuertes (2 puntos o más), para que cada área
  que eligió, donde trabaja o que estudió tenga sitio arriba; las débiles (solo una mención suelta) van después.
  Dentro de cada área, primero los roles que usan más habilidades que ya tiene.
- Si el agente refinó las sugerencias (perfil["sugerencias"]), esas van primero.
- El tablero usa la misma lógica en static/sugerencias.js; tests/test_sugerencias.py comprueba que ambas
  den exactamente lo mismo.
"""
from __future__ import annotations

import functools
import json
import re
import unicodedata
from pathlib import Path

MAPA = Path(__file__).with_name("sugerencias.json")
MAX_HABILIDADES, MAX_ROLES = 12, 8
PESOS = {"interes": 3, "puesto_actual": 3, "estudios": 2, "otros": 1}
FUERTE = 2  # puntos mínimos para que un área entre en los primeros turnos


@functools.lru_cache(maxsize=1)
def cargar_mapa() -> dict:
    return json.loads(MAPA.read_text(encoding="utf-8"))


def areas() -> list[str]:
    return [a["area"] for a in cargar_mapa()["areas"]]


def normalizar(texto) -> str:
    """Minúsculas, sin tildes y sin signos: «Diseño UX/UI» → «diseno ux ui»."""
    t = unicodedata.normalize("NFD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _menciona(texto: str, palabra: str) -> bool:
    """La palabra (ya normalizada o no) aparece al inicio de una palabra del texto normalizado."""
    return f" {normalizar(palabra)}" in f" {texto} "


def _coincide(a: str, b: str) -> bool:
    """Misma habilidad aunque una sea más específica: «Excel» ~ «Excel avanzado», «LLM» ~ «IA generativa (LLM)»."""
    na, nb = normalizar(a), normalizar(b)
    return bool(na and nb) and (f" {na} " in f" {nb} " or f" {nb} " in f" {na} ")


def _lista(valor) -> list:
    return valor if isinstance(valor, list) else []


def _turnos(grupos: list[list]) -> list:
    """Uno de cada grupo por vuelta: [[a1, a2], [b1]] → [a1, b1, a2]."""
    return [g[k] for k in range(max(map(len, grupos), default=0)) for g in grupos if k < len(g)]


def _por_turnos(activas: list[dict], elementos) -> list:
    fuertes = [elementos(x) for x in activas if x["puntos"] >= FUERTE]
    debiles = [elementos(x) for x in activas if x["puntos"] < FUERTE]
    return _turnos(fuertes) + _turnos(debiles)


def _razon(rol: dict, fuentes: list[str], ya: list[str], perfil: dict) -> str:
    if ya:
        return f"Usa {' y '.join(ya[:2])}, que ya tienes."
    if "puesto_actual" in fuentes:
        return f"Encaja con tu experiencia como {str(perfil.get('puesto_actual')).strip().rstrip('.')}."
    if "estudios" in fuentes:
        return f"Encaja con lo que estudiaste ({str(perfil.get('estudios')).strip().rstrip('.')})."
    return rol["razon"]


def sugerir(perfil: dict, mapa: dict | None = None) -> dict:
    mapa = mapa or cargar_mapa()
    intereses = {normalizar(x) for x in _lista(perfil.get("intereses"))}
    textos = {"puesto_actual": normalizar(perfil.get("puesto_actual")), "estudios": normalizar(perfil.get("estudios")),
              "otros": normalizar(f"{perfil.get('experiencia') or ''} {perfil.get('intereses_otra') or ''}")}
    tengo = [str(h) for h in _lista(perfil.get("habilidades"))]

    activas = []
    for i, area in enumerate(mapa["areas"]):
        fuentes = ["interes"] if normalizar(area["area"]) in intereses else []
        fuentes += [f for f, texto in textos.items() if texto and any(_menciona(texto, p) for p in area["palabras"])]
        if fuentes:
            activas.append({"area": area, "i": i, "puntos": sum(PESOS[f] for f in fuentes), "fuentes": fuentes})
    activas.sort(key=lambda x: (-x["puntos"], x["i"]))

    agente = perfil.get("sugerencias") if isinstance(perfil.get("sugerencias"), dict) else {}
    habilidades, vistas = [], set()
    for origen, nombres in (("agente", _lista(agente.get("habilidades"))),
                            ("mapa", _por_turnos(activas, lambda x: x["area"]["habilidades"]))):
        for nombre in nombres:
            n = normalizar(nombre)
            if n and n not in vistas and (origen == "agente" or sum(h["origen"] == "mapa" for h in habilidades) < MAX_HABILIDADES):
                vistas.add(n)
                habilidades.append({"nombre": nombre, "origen": origen})

    def roles_del_area(x):
        con_ya = [(rol, [h for h in rol.get("habilidades", []) if any(_coincide(h, t) for t in tengo)])
                  for rol in x["area"]["roles"]]
        orden = sorted(range(len(con_ya)), key=lambda j: (-len(con_ya[j][1]), j))
        return [(con_ya[j][0], x["fuentes"], con_ya[j][1]) for j in orden]
    candidatos = _por_turnos(activas, roles_del_area)
    roles, vistos = [], set()
    for r in _lista(agente.get("roles")):
        n = normalizar(r.get("rol"))
        if n and n not in vistos:
            vistos.add(n)
            roles.append({"rol": r["rol"], "razon": r.get("razon") or "", "origen": "agente"})
    de_mapa = 0
    for rol, fuentes, ya in candidatos:
        n = normalizar(rol["rol"])
        if n not in vistos and de_mapa < MAX_ROLES:
            vistos.add(n)
            de_mapa += 1
            roles.append({"rol": rol["rol"], "razon": _razon(rol, fuentes, ya, perfil), "origen": "mapa"})
    return {"areas": [x["area"]["area"] for x in activas], "habilidades": habilidades, "roles": roles}
