import sys
import zipfile
from pathlib import Path

import pytest

import app as tablero
from conftest import empresa
from oportunidades import config, perfil as pf

sys.path.insert(0, str(tablero.ROOT / "scripts"))
import construir_demo  # noqa: E402


def _textos(carpeta: Path) -> dict[str, str]:
    textos = {p.name: p.read_text(encoding="utf-8") for p in carpeta.iterdir() if p.suffix in {".html", ".js", ".css"}}
    with zipfile.ZipFile(carpeta / "oportunidades-demo.xlsx") as z:
        textos["xlsx"] = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xml"))
    return textos


@pytest.fixture
def demo(tmp_path, store, monkeypatch):
    """Construye la demo con un perfil y una base «reales» presentes: no deben aparecer en ella."""
    perfil = pf.importar(config.ROOT / "profile.example.yaml")
    perfil.update(nombre="Persona Secreta Real", titular="Titular secreto")
    pf.guardar(perfil)
    empresa(store, "Empresa Secreta SRL")
    monkeypatch.setattr(construir_demo, "DESTINO", tmp_path / "no-usar")
    destino = tmp_path / "publica"
    construir_demo.construir(destino)
    return destino


def test_la_demo_es_estatica_y_solo_tiene_datos_inventados(demo):
    t = _textos(demo)
    assert {"index.html", "demo-datos.js", "app.js", "style.css", "xlsx"} <= set(t)
    todo = "\n".join(t.values())
    for secreto in ("Persona Secreta Real", "Titular secreto", "Empresa Secreta SRL", str(Path.home()),
                    str(Path.home()).replace("\\", "\\\\"), str(tablero.ROOT)):
        assert secreto not in todo
    assert "Ana Ejemplo Pérez" in t["demo-datos.js"] and "Distribuidora del Caribe (demo)" in t["demo-datos.js"]
    assert "_path" not in t["demo-datos.js"]
    html = t["index.html"]
    assert "/api/" not in html and "/static/" not in html
    assert 'class="demo-tag"' in html and "instala el skill para usarlo con tu perfil" in html
    assert 'id="instalar"' in html and "y ábreme el panel." in html and tablero.REPO in html
    assert "Llenar mi perfil" not in html and 'href="oportunidades-demo.xlsx"' in html


def test_cada_empresa_tiene_su_detalle_y_la_fecha_de_construccion(demo):
    import datetime as dt
    js = (demo / "demo-datos.js").read_text(encoding="utf-8")
    assert f'window.DEMO_FECHA = "{dt.date.today().isoformat()}";' in js  # app.js mueve las fechas desde aquí
    for i in range(1, 7):
        assert f'"/api/empresas/{i}"' in js


def test_docs_esta_al_dia(demo):
    """docs/ (la demo publicada) debe reconstruirse cuando cambian templates/ o static/."""
    for nombre in ("index.html", "app.js", "style.css", "sugerencias.js"):
        publicado = (tablero.ROOT / "docs" / nombre).read_text(encoding="utf-8").replace("\r\n", "\n")
        nuevo = (demo / nombre).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert publicado == nuevo, f"docs/{nombre} está desactualizado: python scripts/construir_demo.py"


def test_la_app_local_no_cambia():
    html = tablero.crear_app().test_client().get("/").get_data(as_text=True)
    assert 'href="/api/excel"' in html and "Llenar mi perfil" in html and 'id="agente"' in html
    assert "demo-tag" not in html and "demo-datos.js" not in html and 'id="instalar"' not in html
