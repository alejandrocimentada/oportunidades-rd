import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from oportunidades import config, perfil as pf

ROOT = config.ROOT


def archivos_del_repo():
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and not any(
        x in {".git", "__pycache__", ".pytest_cache", "data"} for x in p.relative_to(ROOT).parts))


def test_ruta_por_defecto_en_config_del_usuario(monkeypatch, tmp_path):
    monkeypatch.delenv(config.PROFILE_ENV, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert config.profile_path() == (tmp_path / ".config" / "oportunidades-rd" / "profile.yaml").resolve()


@pytest.mark.parametrize("dentro", ["profile.yaml", "data/profile.yaml", "scripts/x/profile.yaml"])
def test_nunca_dentro_del_repo(monkeypatch, dentro):
    monkeypatch.setenv(config.PROFILE_ENV, str(ROOT / dentro))
    with pytest.raises(config.ConfigError):
        config.profile_path()
    with pytest.raises(config.ConfigError):
        pf.guardar(pf.plantilla(), ROOT / dentro)
    assert not (ROOT / dentro).exists()


def test_guardar_y_leer_sin_tocar_el_repo():
    antes = archivos_del_repo()
    data = pf.set_campo(pf.cargar(), "habilidades", "Python; SQL ; Power Automate")
    data = pf.set_campo(data, "preferencias.salario_minimo_dop", "RD$100,000")
    data = pf.set_campo(data, "ia.proveedor", "claude")
    path = pf.guardar(data)
    assert path.exists() and not config.dentro_del_repo(path)
    again = pf.cargar()
    assert again["habilidades"] == ["Python", "SQL", "Power Automate"]
    assert again["preferencias"]["salario_minimo_dop"] == 100000 and again["ia"]["proveedor"] == "claude"
    assert archivos_del_repo() == antes


def test_valores_invalidos():
    with pytest.raises(pf.PerfilError):
        pf.set_campo(pf.cargar(), "ia.proveedor", "gemini-pirata")
    with pytest.raises(pf.PerfilError):
        pf.set_campo(pf.cargar(), "cedula", "001-0000000-1")  # campos no previstos no se aceptan


def test_ejemplo_es_valido_y_con_datos_falsos():
    data = pf.importar(ROOT / "profile.example.yaml")
    assert data["nombre"] == "Ana Ejemplo Pérez" and "ejemplo" in data["enlaces"]["portafolio"]
    assert data["preferencias"]["salario_minimo_dop"] == 100000
    assert pf.faltantes(data) == []
    raw = yaml.safe_load((ROOT / "profile.example.yaml").read_text(encoding="utf-8"))
    assert "@" not in yaml.safe_dump(raw)  # sin correos


def test_script_show_sin_perfil_y_set():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "perfil.py"), "show"], capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 2 and "Todavía no hay perfil" in r.stdout
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "perfil.py"), "set", "roles_objetivo",
                        "Ingeniero de IA; Automatización"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert pf.cargar()["roles_objetivo"] == ["Ingeniero de IA", "Automatización"]


def test_gitignore_protege_datos_y_perfil():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/*" in gi and "profile.yaml" in gi
