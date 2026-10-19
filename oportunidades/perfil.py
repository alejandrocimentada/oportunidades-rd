"""Perfil del usuario: roles, habilidades, experiencia, preferencias y proveedor de IA.

Se guarda en ~/.config/oportunidades-rd/profile.yaml (ver config.profile_path), nunca en el repo.
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import tempfile
from pathlib import Path

import yaml

from . import config

PROVEEDORES = {"agente", "claude", "openai", "ninguno"}
MODALIDADES = {"presencial", "hibrido", "remoto"}

# Campos de texto libre o listas que se pueden cambiar con `perfil.py set`.
LISTAS = {"roles_objetivo", "habilidades", "industrias", "idiomas"}
ESCALARES = {
    "nombre", "titular", "experiencia", "anos_experiencia", "ubicacion",
    "preferencias.dias", "preferencias.modalidad", "preferencias.dias_remotos",
    "preferencias.salario_minimo_dop", "preferencias.salario_flexible_startups", "enlaces.portafolio", "enlaces.github",
    "enlaces.linkedin", "ia.proveedor", "ia.modelo",
}


def plantilla() -> dict:
    return {
        "nombre": "",
        "titular": "",
        "roles_objetivo": [],
        "habilidades": [],
        "experiencia": "",
        "anos_experiencia": 0,
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
        "industrias": [],
        "ia": {"proveedor": "agente", "modelo": ""},
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
        data = _merge(data, raw)
    return validar(data)


def validar(data: dict) -> dict:
    for campo in LISTAS:
        valor = data.get(campo) or []
        if isinstance(valor, str):
            valor = [x.strip() for x in valor.split(";") if x.strip()]
        data[campo] = [str(x).strip() for x in valor if str(x).strip()]
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
    return data


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
    return validar(_merge(data or plantilla(), raw))


def faltantes(data: dict) -> list[str]:
    """Campos importantes que siguen vacíos (para que el agente pregunte)."""
    out = []
    for campo in ("roles_objetivo", "habilidades", "experiencia", "idiomas", "industrias"):
        if not data.get(campo):
            out.append(campo)
    if not data["preferencias"].get("salario_minimo_dop"):
        out.append("preferencias.salario_minimo_dop")
    return out
