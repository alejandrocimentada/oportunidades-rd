"""Descarga educada de páginas públicas.

- Respeta robots.txt (si una página está prohibida, no se descarga).
- Máximo 1 petición cada 3 segundos por sitio.
- User-Agent claro que dice quién es y para qué.
- Guarda las páginas en caché 24 horas (no vuelve a pedir lo mismo).
- Nunca descarga portales de empleo (LinkedIn, Computrabajo, Indeed…).
- No intenta saltarse logins, CAPTCHAs ni protecciones anti-bots.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib import robotparser
from urllib.parse import urlsplit

from . import __version__, config
from .texto import es_portal_bloqueado

USER_AGENT = (f"OportunidadesRD/{__version__} (busqueda personal de empleo; respeta robots.txt; "
              "+https://github.com/alejandrocimentada/oportunidades-rd)")
INTERVALO_SEGUNDOS = 3.0
CACHE_HORAS = 24
TIMEOUT = 20


@dataclass
class Respuesta:
    url: str
    status: int
    texto: str
    content_type: str = ""
    url_final: str = ""
    desde_cache: bool = False


class Prohibido(Exception):
    """robots.txt no permite esta URL."""


class Bloqueado(Exception):
    """URL de un portal de empleo que no se rastrea."""


Transporte = Callable[[str, dict], Respuesta]


_CHARSET = re.compile(rb"""charset\s*=\s*["']?([A-Za-z0-9_.:-]+)""", re.I)


def decodificar(contenido: bytes, content_type: str = "") -> str:
    """Texto de una respuesta. Sin charset en la cabecera, no se asume ISO-8859-1 (lo que hace requests y
    rompe los acentos): se mira el <meta charset> de la página, luego se prueba UTF-8 y por último cp1252."""
    candidatos = []
    m = _CHARSET.search(content_type.encode("latin-1", "ignore"))
    if m:
        candidatos.append(m.group(1).decode())
    m = _CHARSET.search(contenido[:4096])
    if m:
        candidatos.append(m.group(1).decode())
    for cs in candidatos + ["utf-8"]:
        try:
            return contenido.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return contenido.decode("cp1252", errors="replace")


def transporte_requests(url: str, headers: dict) -> Respuesta:
    import requests

    r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    ct = r.headers.get("Content-Type", "")
    return Respuesta(url=url, status=r.status_code, texto=decodificar(r.content, ct), content_type=ct, url_final=r.url)


@dataclass
class Fetcher:
    transporte: Transporte = transporte_requests
    cache_dir: Path | None = None
    intervalo: float = INTERVALO_SEGUNDOS
    cache_horas: float = CACHE_HORAS
    reloj: Callable[[], float] = time.monotonic
    dormir: Callable[[float], None] = time.sleep
    ahora: Callable[[], float] = time.time
    usar_cache: bool = True
    _ultimo: dict = field(default_factory=dict)
    _robots: dict = field(default_factory=dict)
    peticiones: list = field(default_factory=list)  # registro (url, momento) para depurar/pruebas

    def __post_init__(self):
        if self.cache_dir is None:
            self.cache_dir = config.cache_dir()
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    # -- caché ----------------------------------------------------------------------------
    def _cache_file(self, url: str) -> Path:
        return Path(self.cache_dir) / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")

    def _leer_cache(self, url: str) -> Respuesta | None:
        if not self.usar_cache:
            return None
        f = self._cache_file(url)
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if self.ahora() - data["guardado"] > self.cache_horas * 3600:
            return None
        return Respuesta(url=url, status=data["status"], texto=data["texto"],
                         content_type=data.get("content_type", ""), url_final=data.get("url_final", url),
                         desde_cache=True)

    def _guardar_cache(self, resp: Respuesta) -> None:
        if resp.status >= 500:
            return
        self._cache_file(resp.url).write_text(json.dumps({
            "url": resp.url, "status": resp.status, "texto": resp.texto, "content_type": resp.content_type,
            "url_final": resp.url_final, "guardado": self.ahora()}, ensure_ascii=False), encoding="utf-8")

    # -- ritmo ----------------------------------------------------------------------------
    def _esperar_turno(self, sitio: str) -> None:
        ultimo = self._ultimo.get(sitio)
        if ultimo is not None:
            falta = self.intervalo - (self.reloj() - ultimo)
            if falta > 0:
                self.dormir(falta)
        self._ultimo[sitio] = self.reloj()

    def _pedir(self, url: str) -> Respuesta:
        cache = self._leer_cache(url)
        if cache:
            return cache
        sitio = urlsplit(url).netloc.lower()
        self._esperar_turno(sitio)
        self.peticiones.append((url, self.reloj()))
        resp = self.transporte(url, {"User-Agent": USER_AGENT, "Accept-Language": "es-DO,es;q=0.9,en;q=0.7"})
        resp.url = url
        self._guardar_cache(resp)
        return resp

    # -- robots.txt -----------------------------------------------------------------------
    def _parser(self, url: str) -> robotparser.RobotFileParser:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                resp = self._pedir(base + "/robots.txt")
                status, texto = resp.status, resp.texto
            except Exception:  # sin red o error: tratamos como "sin robots.txt" = permitido
                status, texto = 404, ""
            if status in (401, 403):
                rp.disallow_all = True
            elif status >= 400:
                rp.allow_all = True
            else:
                rp.parse(texto.splitlines())
            self._robots[base] = rp
        return self._robots[base]

    def permitido(self, url: str) -> bool:
        return self._parser(url).can_fetch(USER_AGENT, url)

    def get(self, url: str) -> Respuesta:
        if es_portal_bloqueado(url):
            raise Bloqueado(url)
        if not self.permitido(url):
            raise Prohibido(url)
        return self._pedir(url)
