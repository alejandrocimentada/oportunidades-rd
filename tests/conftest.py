from __future__ import annotations

from pathlib import Path

import pytest

from oportunidades import config, perfil as pf
from oportunidades.crawler import Fetcher, Respuesta
from oportunidades.db import Store

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    """Cada prueba usa su propia carpeta de datos y su propio perfil, fuera del repo, sin claves de IA."""
    monkeypatch.setenv(config.DATA_ENV, str(tmp_path / "data"))
    monkeypatch.setenv(config.PROFILE_ENV, str(tmp_path / "home" / ".config" / "oportunidades-rd" / "profile.yaml"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def perfil():
    return pf.importar(config.ROOT / "profile.example.yaml")


@pytest.fixture
def store():
    s = Store()
    yield s
    s.close()


class FakeWeb:
    """Transporte falso: mapa URL → (status, texto). Lo no definido devuelve 404."""

    def __init__(self, paginas: dict[str, tuple[int, str] | str]):
        self.paginas = {k: (v if isinstance(v, tuple) else (200, v)) for k, v in paginas.items()}
        self.pedidas: list[tuple[str, dict]] = []

    def __call__(self, url: str, headers: dict) -> Respuesta:
        self.pedidas.append((url, headers))
        status, texto = self.paginas.get(url, (404, "not found"))
        return Respuesta(url=url, status=status, texto=texto, url_final=url)

    def urls(self) -> list[str]:
        return [u for u, _ in self.pedidas]


class Reloj:
    def __init__(self):
        self.t = 1000.0
        self.dormido: list[float] = []

    def __call__(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.dormido.append(s)
        self.t += s


@pytest.fixture
def web_y_fetcher(tmp_path):
    def crear(paginas, **kw):
        web = FakeWeb(paginas)
        reloj = Reloj()
        f = Fetcher(transporte=web, cache_dir=tmp_path / "cache", reloj=reloj, dormir=reloj.dormir,
                    ahora=lambda: reloj.t, **kw)
        return web, f, reloj
    return crear
