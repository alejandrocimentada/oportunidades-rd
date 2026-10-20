"""Habilidades y roles sugeridos SIN IA: un mapa local de áreas (sugerencias.json) y el índice de ESCO (esco.json).

Entra lo que el usuario eligió y contó en el asistente del perfil: áreas de interés, estudios, último puesto,
experiencia, habilidades y roles. Sale una lista ordenada de habilidades y de roles, cada rol con un «por qué».

- Un área cuenta si la eligió (peso 3) o si sus palabras aparecen en su puesto (3), sus estudios (2) u otro
  texto (1). Las áreas se ordenan por esos puntos.
- Los roles y habilidades se reparten POR TURNOS entre las áreas fuertes (2 puntos o más), para que cada área
  que eligió, donde trabaja o que estudió tenga sitio arriba; las débiles (solo una mención suelta) van después.
  Dentro de cada área, primero los roles que usan más habilidades que ya tiene.
- ESCO (clasificación europea de ocupaciones y habilidades) suma un turno más: ocupaciones parecidas a su
  puesto o que piden 2 o más de sus habilidades, y las habilidades esenciales de esas ocupaciones y de los roles
  que eligió. También da el buscador de habilidades del paso 3 (buscar_habilidades), sobre una lista de nombres
  cortos: parte de ESCO, competencias de ESCO reescritas y herramientas curadas (ver scripts/construir_esco.py).
- Si el agente refinó las sugerencias (perfil["sugerencias"]), esas van primero.
- El tablero usa la misma lógica en static/sugerencias.js; tests/test_sugerencias.py y tests/test_esco.py
  comprueban que ambas den exactamente lo mismo.
"""
from __future__ import annotations

import functools
import json
import re
import unicodedata
from pathlib import Path

MAPA = Path(__file__).with_name("sugerencias.json")
ESCO = Path(__file__).resolve().parent.parent / "static" / "esco.json"  # lo crea scripts/construir_esco.py
MAX_HABILIDADES, MAX_ROLES = 12, 8
MAX_ESCO_HABILIDADES, MAX_ESCO_ROLES = 6, 4
MAX_RESULTADOS = 8  # del buscador
PESOS = {"interes": 3, "puesto_actual": 3, "estudios": 2, "otros": 1}
FUERTE = 2  # puntos mínimos para que un área entre en los primeros turnos
MIN_ETIQUETA_OCUPACION = 5  # nombres de ocupación más cortos no se buscan dentro del puesto
# Palabras que no cuentan como inicio de palabra en el buscador: «as» no debe encontrar «work as a team».
VACIAS = frozenset("a al an and as at by con de del e el en for in la las los o of on or para por the to u un una y with".split())


@functools.lru_cache(maxsize=1)
def cargar_mapa() -> dict:
    return json.loads(MAPA.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def cargar_esco() -> dict | None:
    """El índice de ESCO preparado para buscar, o None si todavía no se construyó."""
    return preparar_esco(json.loads(ESCO.read_text(encoding="utf-8"))) if ESCO.exists() else None


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


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _turnos(grupos: list[list]) -> list:
    """Uno de cada grupo por vuelta: [[a1, a2], [b1]] → [a1, b1, a2]."""
    return [g[k] for k in range(max(map(len, grupos), default=0)) for g in grupos if k < len(g)]


def _por_turnos(activas: list[dict], elementos, extra: list) -> list:
    """Turnos entre las áreas fuertes y el grupo extra (ESCO); las áreas débiles, después."""
    fuertes = [elementos(x) for x in activas if x["puntos"] >= FUERTE] + ([extra] if extra else [])
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


# -- ESCO: índice, buscador y ocupaciones -------------------------------------------------------
def preparar_esco(datos: dict) -> dict:
    """Normaliza una vez las etiquetas del índice (esco.json) para buscar rápido."""
    hn = [[normalizar(es), normalizar(en), [normalizar(s) for s in sinonimos]] for es, en, sinonimos, *_ in datos["h"]]
    por_nombre = {}
    for i, (es, en, sinonimos) in enumerate(hn):
        for n in (es, en, *sinonimos):
            if n and n not in por_nombre:
                por_nombre[n] = i  # el primero gana: el índice va de la habilidad más usada a la menos usada
    # Nombres de ocupación separados por «/» («camarero/camarera» → «camarero», «camarera»), sin los muy cortos.
    formas = lambda etiquetas: [n for n in (normalizar(f) for e in etiquetas for f in e.split("/"))
                                if len(n) >= MIN_ETIQUETA_OCUPACION]
    on = [formas([es, en, *alternativas]) for es, en, alternativas, _ in datos["o"]]
    principal = [set(formas([es, en])) for es, en, _, _ in datos["o"]]
    return {"h": datos["h"], "hn": hn, "o": datos["o"], "on": on, "principal": principal, "por_nombre": por_nombre,
            "eq": datos.get("equivalencias") or {}}


def _variantes(texto: str, esco: dict) -> list[str]:
    """El texto normalizado y, si tiene palabras de RD, también con las de ESCO: «contador» → «contable»."""
    cambiado = " ".join(esco["eq"].get(p, p) for p in texto.split(" "))
    return [texto] if cambiado == texto else [texto, cambiado]


def _partes(rol: dict) -> list[str]:
    """Para no repetir roles: ESCO escribe «enfermero/enfermera»; cada forma cuenta por separado."""
    return [p for p in (normalizar(x) for x in (rol["rol"].split("/") if rol["origen"] == "esco" else [rol["rol"]])) if p]


def _repetido(partes: list[str], nombre: str, aceptados: list[tuple[str, list[str]]]) -> bool:
    return (any(f" {p} " in f" {n} " for n, _ in aceptados for p in partes)
            or any(f" {p} " in f" {nombre} " for _, ps in aceptados for p in ps))


def _nivel(nombre: str, consulta: str) -> int:
    """0: igual; 1: el nombre empieza por lo escrito; 2: otra palabra del nombre empieza por lo escrito (sin contar
    «de», «as», etc.); -1: no coincide. Nunca a mitad de palabra: «ual» no encuentra «manual»."""
    if nombre == consulta:
        return 0
    if nombre.startswith(consulta):
        return 1
    palabras = nombre.split(" ")
    return 2 if any(p not in VACIAS and " ".join(palabras[j:]).startswith(consulta)
                    for j, p in enumerate(palabras) if j) else -1


def buscar_habilidades(consulta: str, esco: dict | None = None, n: int = MAX_RESULTADOS) -> list[dict]:
    """Autocompletar desde 2 letras, en español, inglés o sinónimos, sin tildes. Orden: igual a lo escrito, empieza
    por lo escrito, una palabra empieza por lo escrito; dentro de cada grupo, primero los nombres y luego los
    sinónimos, y de la más usada a la menos (el índice ya viene así: por número de ocupaciones de ESCO)."""
    esco = esco or cargar_esco()
    q = normalizar(consulta)
    if not esco or len(q) < 2:
        return []
    consultas = _variantes(q, esco)
    mejores = []
    for i, (es, en, sinonimos) in enumerate(esco["hn"]):
        mejor = None
        for k, t in enumerate((es, en, *sinonimos)):
            for v in consultas:
                nivel = _nivel(t, v) if t else -1
                if nivel >= 0 and (mejor is None or (nivel, k) < mejor):
                    mejor = (nivel, k)
        if mejor:
            mejores.append((mejor[0], mejor[1] >= 2, i, mejor[1]))
    mejores.sort()
    out = []
    for _, _, i, k in mejores[:n]:
        es, en, sinonimos = esco["h"][i][:3]
        out.append({"es": es, "en": en, "sinonimo": sinonimos[k - 2] if k >= 2 else ""})
    return out


def _de_esco(perfil: dict, esco: dict | None) -> tuple[list[dict], list[str]]:
    """Roles y habilidades que ESCO sugiere: ocupaciones como su puesto, o que piden 2+ de sus habilidades."""
    if not esco:
        return [], []
    tengo = {esco["por_nombre"][n] for n in (normalizar(h) for h in _lista(perfil.get("habilidades")))
             if n in esco["por_nombre"]}
    puestos = _variantes(normalizar(perfil.get("puesto_actual")), esco)
    mis_roles = {v for r in _lista(perfil.get("roles_objetivo")) for v in _variantes(normalizar(r), esco)}
    ocupaciones = []
    for j, etiquetas in enumerate(esco["on"]):
        en_puesto = [e for e in etiquetas if any(p and f" {e} " in f" {p} " for p in puestos)]
        por_puesto = bool(en_puesto)
        por_rol = any(e in mis_roles for e in etiquetas)
        comunes = [i for i in esco["o"][j][3] if i in tengo]
        if por_puesto or por_rol or len(comunes) >= 2:
            # Su nombre principal en el puesto cuenta más que un nombre alternativo («contable» > «administrativo contable»).
            principal = any(e in esco["principal"][j] for e in en_puesto)
            puntos = (100 if por_puesto else 0) + (10 if principal else 0) + (50 if por_rol else 0) + len(comunes)
            ocupaciones.append((-puntos, j, por_puesto, por_rol, comunes))
    ocupaciones.sort(key=lambda x: x[:2])

    roles = []
    for _, j, por_puesto, por_rol, comunes in ocupaciones:
        if len(roles) < MAX_ESCO_ROLES and (por_puesto or len(comunes) >= 2):
            razon = ("Ocupación de ESCO parecida a tu trabajo actual." if por_puesto else
                     f"Según ESCO, pide {' y '.join(esco['h'][i][0] for i in comunes[:2])}, que ya tienes.")
            roles.append({"rol": _mayuscula(esco["o"][j][0]), "razon": razon, "origen": "esco"})
    habilidades, vistas = [], set(tengo)
    for _, j, *_ in ocupaciones:
        for i in esco["o"][j][3]:
            if i not in vistas and len(habilidades) < MAX_ESCO_HABILIDADES:
                vistas.add(i)
                habilidades.append(_mayuscula(esco["h"][i][0]))
    return roles, habilidades


_AUTO = object()


def sugerir(perfil: dict, mapa: dict | None = None, esco=_AUTO) -> dict:
    mapa = mapa or cargar_mapa()
    esco = cargar_esco() if esco is _AUTO else esco
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
    roles_esco, habilidades_esco = _de_esco(perfil, esco)

    agente = perfil.get("sugerencias") if isinstance(perfil.get("sugerencias"), dict) else {}
    habilidades, vistas, sugeridas = [], set(), 0
    candidatas = [(h, "agente") for h in _lista(agente.get("habilidades"))] + _por_turnos(
        activas, lambda x: [(h, "mapa") for h in x["area"]["habilidades"]], [(h, "esco") for h in habilidades_esco])
    for nombre, origen in candidatas:
        n = normalizar(nombre)
        if n and n not in vistas and (origen == "agente" or sugeridas < MAX_HABILIDADES):
            vistas.add(n)
            sugeridas += origen != "agente"
            habilidades.append({"nombre": nombre, "origen": origen})

    def roles_del_area(x):
        con_ya = [(rol, [h for h in rol.get("habilidades", []) if any(_coincide(h, t) for t in tengo)])
                  for rol in x["area"]["roles"]]
        orden = sorted(range(len(con_ya)), key=lambda j: (-len(con_ya[j][1]), j))
        return [{"rol": con_ya[j][0]["rol"], "razon": _razon(con_ya[j][0], x["fuentes"], con_ya[j][1], perfil),
                 "origen": "mapa"} for j in orden]
    candidatos = [{"rol": r.get("rol") or "", "razon": r.get("razon") or "", "origen": "agente"}
                  for r in _lista(agente.get("roles")) if isinstance(r, dict)]
    candidatos += _por_turnos(activas, roles_del_area, roles_esco)
    roles, aceptados, sugeridos = [], [], 0
    for r in candidatos:
        n, partes = normalizar(r["rol"]), _partes(r)
        if n and not _repetido(partes, n, aceptados) and (r["origen"] == "agente" or sugeridos < MAX_ROLES):
            aceptados.append((n, partes))
            sugeridos += r["origen"] != "agente"
            roles.append(r)
    return {"areas": [x["area"]["area"] for x in activas], "habilidades": habilidades, "roles": roles}
