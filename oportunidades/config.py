"""Rutas del proyecto: perfil (fuera del repo), base de datos, caché y documentos.

- El perfil vive en ~/.config/oportunidades-rd/profile.yaml (o en OPORTUNIDADES_RD_PROFILE).
  Nunca dentro de la carpeta del proyecto.
- Los datos (SQLite, caché, Excel, documentos generados) viven en <proyecto>/data
  (o en OPORTUNIDADES_RD_DATA). La carpeta data/ está en .gitignore.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_ENV = "OPORTUNIDADES_RD_PROFILE"
DATA_ENV = "OPORTUNIDADES_RD_DATA"


class ConfigError(ValueError):
    """Ruta no permitida."""


def dentro_del_repo(path: Path) -> bool:
    path = path.resolve()
    return path == ROOT or ROOT in path.parents


def profile_path() -> Path:
    raw = os.environ.get(PROFILE_ENV)
    path = Path(raw).expanduser() if raw else Path.home() / ".config" / "oportunidades-rd" / "profile.yaml"
    path = path.resolve()
    if dentro_del_repo(path):
        raise ConfigError(
            f"El perfil no puede guardarse dentro de la carpeta del proyecto ({ROOT}). "
            "Usa ~/.config/oportunidades-rd/profile.yaml.")
    return path


def data_dir() -> Path:
    raw = os.environ.get(DATA_ENV)
    path = Path(raw).expanduser().resolve() if raw else ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "oportunidades.db"


def cache_dir() -> Path:
    path = data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def docs_dir() -> Path:
    path = data_dir() / "documentos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def xlsx_path() -> Path:
    return data_dir() / "oportunidades.xlsx"
