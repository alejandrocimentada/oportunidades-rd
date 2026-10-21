"""Perfil del usuario: intereses, experiencia, habilidades, roles, preferencias y proveedor de IA.

Se guarda en ~/.config/oportunidades-rd/profile.yaml (ver config.profile_path), nunca en el repo.
Los perfiles anteriores a la v1.1 (con «industrias» y sin «intereses») se migran al cargarlos.
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import tempfile
from pathlib import Path

import yaml

from . import config, sugerencias as sg

PROVEEDORES = {"agente", "claude", "openai", "ninguno"}
MODALIDADES = {"presencial", "hibrido", "remoto"}

# Campos de texto libre o listas que se pueden cambiar con `perfil.py set`.
LISTAS = {"intereses", "roles_objetivo", "habilidades", "industrias", "idiomas"}
ESCALARES = {
    "nombre", "edad", "email", "tiene_experiencia", "roles_abiertos", "titular", "intereses_otra", "estudios", "puesto_actual", "experiencia", "anos_experiencia", "ubicacion",
    "preferencias.dias", "preferencias.modalidad", "preferencias.dias_remotos",
    "preferencias.salario_minimo_dop", "preferencias.salario_flexible_startups", "enlaces.portafolio", "enlaces.github",
    "enlaces.linkedin", "ia.proveedor", "ia.modelo",
}


def plantilla() -> dict:
    return {
        "nombre": "",
        "edad": 0,  # opcional
        "email": "",  # opcional; solo se guarda en esta computadora
        "titular": "",
        # Áreas de oportunidades/sugerencias.json (paso 1); lo que no está en la lista va en intereses_otra.
        "intereses": [],
        "intereses_otra": "",
        "estudios": "",
        "puesto_actual": "",  # último puesto o el actual
        "tiene_experiencia": None,  # True / False; None = sin responder
        "anos_experiencia": 0,
        "experiencia": "",  # resumen opcional de 2-3 frases (se usa en las cartas)
        "habilidades": [],
        "roles_objetivo": [],
        "roles_abiertos": False,  # «No sé todavía»: el agente propone roles
        "idiomas": [],
        "ubicacion": "Santo Domingo",
        "preferencias": {
            "dias": "lunes a viernes",
            "modalidad": "hibrido",
            "dias_remotos": 0,
            "salario_minimo_dop": 0,
            # En startups, un salario base menor (con equity o variable) es "a conversar", no una alerta.
            "salario_flexible_startups": False,
        },
        "enlaces": {"portafolio": "", "github": "", "linkedin": ""},
        "industrias": [],  # sectores preferidos (opcional; antes era un paso del asistente)
        "ia": {"proveedor": "agente", "modelo": ""},
        # Sugerencias refinadas por el agente (perfil.py sugerencias): el tablero las muestra primero.
        "sugerencias": {"habilidades": [], "roles": []},
        "actualizado": "",
    }


class PerfilError(ValueError):
    """Valor de perfil inválido."""


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def existe(path: Path | None = None) -> bool:
    return (path or config.profile_path()).exists()


def cargar(path: Path | None = None) -> dict:
    path = path or config.profile_path()
    data = plantilla()
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise PerfilError(f"{path} no tiene un perfil válido.")
        data = _merge(data, migrar(raw))
    return validar(data)


def migrar(raw: dict) -> dict:
    """Perfil anterior a la v1.1 (sin la clave «intereses»): deduce las áreas de sus antiguas «industrias».

    Solo cuando falta la clave: si el usuario ya guardó con el asistente nuevo y vació sus intereses, se respeta.
    """
    if "intereses" in raw or not raw.get("industrias"):
        return raw
    industrias = raw["industrias"]
    if isinstance(industrias, str):
        industrias = industrias.split(";")
    equivalencias = sg.cargar_mapa()["industrias_antiguas"]
    intereses = []
    for industria in industrias:
        for area in equivalencias.get(str(industria).strip().lower(), []):
            if area not in intereses:
                intereses.append(area)
    return {**raw, "intereses": intereses}


def validar(data: dict) -> dict:
    for campo in LISTAS:
        valor = data.get(campo) or []
        if isinstance(valor, str):
            valor = [x.strip() for x in valor.split(";") if x.strip()]
        data[campo] = [str(x).strip() for x in valor if str(x).strip()]
    data["intereses"] = _areas(data["intereses"])
    data["sugerencias"] = _sugerencias(data.get("sugerencias"))
    for campo in ("nombre", "email", "intereses_otra", "estudios", "puesto_actual", "experiencia"):
        data[campo] = str(data.get(campo) or "").strip()
    prov = str(data["ia"].get("proveedor") or "agente").lower()
    if prov not in PROVEEDORES:
        raise PerfilError(f"ia.proveedor debe ser uno de: {', '.join(sorted(PROVEEDORES))}")
    data["ia"]["proveedor"] = prov
    mod = str(data["preferencias"].get("modalidad") or "hibrido").lower().replace("í", "i")
    if mod not in MODALIDADES:
        raise PerfilError(f"preferencias.modalidad debe ser uno de: {', '.join(sorted(MODALIDADES))}")
    data["preferencias"]["modalidad"] = mod
    for clave in ("salario_minimo_dop", "dias_remotos"):
        data["preferencias"][clave] = _entero(data["preferencias"].get(clave), f"preferencias.{clave}")
    flex = data["preferencias"].get("salario_flexible_startups")
    data["preferencias"]["salario_flexible_startups"] = (
        str(flex).strip().lower() in ("true", "1", "si", "sí", "yes") if isinstance(flex, str) else bool(flex))
    data["anos_experiencia"] = _entero(data.get("anos_experiencia"), "anos_experiencia")
    data["edad"] = _entero(data.get("edad"), "edad")
    data["tiene_experiencia"] = _si_no(data.get("tiene_experiencia"))
    data["roles_abiertos"] = _si_no(data.get("roles_abiertos")) is True
    return data


def _si_no(valor):
    """«si»/«no» (o true/false) a True/False; vacío = None (sin responder)."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in ("si", "sí", "true", "1", "yes"):
        return True
    if texto in ("no", "false", "0"):
        return False
    raise PerfilError("Usa «si» o «no».")


def _areas(valores: list[str]) -> list[str]:
    """Cada interés debe ser un área del mapa (sin importar tildes ni mayúsculas); se guarda con su nombre oficial."""
    oficiales = {sg.normalizar(a): a for a in sg.areas()}
    out = []
    for v in valores:
        area = oficiales.get(sg.normalizar(v))
        if not area:
            raise PerfilError(f"Área desconocida: «{v}». Usa: {', '.join(sg.areas())}. "
                              "Si no está en la lista, escríbela en intereses_otra.")
        if area not in out:
            out.append(area)
    return out


def _sugerencias(valor) -> dict:
    valor = valor if isinstance(valor, dict) else {}
    habilidades = [str(h).strip() for h in valor.get("habilidades") or [] if str(h).strip()]
    roles = []
    for r in valor.get("roles") or []:
        r = {"rol": r} if isinstance(r, str) else r
        if not isinstance(r, dict) or not str(r.get("rol") or "").strip():
            raise PerfilError("Cada rol sugerido necesita «rol» (y opcionalmente «razon»).")
        roles.append({"rol": str(r["rol"]).strip(), "razon": str(r.get("razon") or "").strip()})
    return {"habilidades": habilidades, "roles": roles}


def _entero(valor, nombre: str) -> int:
    if valor in (None, ""):
        return 0
    try:
        return int(str(valor).replace(",", "").replace(".", "").replace("RD$", "").strip())
    except ValueError as exc:
        raise PerfilError(f"{nombre} debe ser un número entero.") from exc


def guardar(data: dict, path: Path | None = None) -> Path:
    path = path or config.profile_path()
    if config.dentro_del_repo(path):
        raise config.ConfigError("El perfil no puede guardarse dentro de la carpeta del proyecto.")
    data = validar(data)
    data["actualizado"] = dt.date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
    os.replace(tmp, path)
    return path


def set_campo(data: dict, clave: str, valor: str) -> dict:
    if clave in LISTAS:
        data[clave] = [x.strip() for x in valor.split(";") if x.strip()]
    elif clave in ESCALARES:
        destino = data
        partes = clave.split(".")
        for p in partes[:-1]:
            destino = destino.setdefault(p, {})
        destino[partes[-1]] = valor
    else:
        raise PerfilError(f"Campo desconocido: {clave}. Campos: {', '.join(sorted(LISTAS | ESCALARES))}")
    return validar(data)


def importar(origen: Path, data: dict | None = None) -> dict:
    raw = yaml.safe_load(Path(origen).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise PerfilError(f"{origen} no es un perfil YAML válido.")
    return validar(_merge(data or plantilla(), migrar(raw)))


def faltantes(data: dict) -> list[str]:
    """Campos importantes que siguen vacíos (para que el agente pregunte)."""
    out = []
    for campo in ("intereses", "habilidades", "roles_objetivo", "idiomas"):
        if not data.get(campo) and not (campo == "intereses" and data.get("intereses_otra")) \
                and not (campo == "roles_objetivo" and data.get("roles_abiertos")):
            out.append(campo)
    if not (data.get("estudios") or data.get("puesto_actual") or data.get("experiencia")):
        out.append("estudios / puesto_actual")
    if not data["preferencias"].get("salario_minimo_dop"):
        out.append("preferencias.salario_minimo_dop")
    return out
