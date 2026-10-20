"""Revisión de vacantes en segundo plano para el tablero: rastrea las páginas de empleo de tus empresas
sin bloquear la página (comprobación secundaria: ¿hay vacantes abiertas o no?).

Solo una búsqueda a la vez. El tablero consulta el progreso (líneas del registro y resultado).
La búsqueda solo LEE páginas públicas de empleo (ver crawler.py); nunca envía nada.
"""
from __future__ import annotations

import threading
from typing import Callable

from .crawler import Fetcher
from .servicio import abrir_store, rastrear


class BusquedaEnCurso(RuntimeError):
    """Ya hay una búsqueda corriendo."""


class Busqueda:
    def __init__(self, fetcher_factory: Callable[[], Fetcher] = Fetcher):
        self.fetcher_factory = fetcher_factory
        self._lock = threading.Lock()
        self._hilo: threading.Thread | None = None
        self.corriendo = False
        self.registro: list[str] = []
        self.resultado: dict | None = None
        self.error = ""
        self.total = 0
        self.hechas = 0

    def estado(self) -> dict:
        with self._lock:
            return {"corriendo": self.corriendo, "registro": list(self.registro[-60:]), "total": self.total,
                    "hechas": self.hechas, "error": self.error,
                    "resultado": _resumir(self.resultado) if self.resultado else None}

    def iniciar(self, esperar: bool = False) -> None:
        with self._lock:
            if self.corriendo:
                raise BusquedaEnCurso("Ya hay una revisión en curso.")
            self.corriendo, self.registro, self.resultado, self.error = True, [], None, ""
            self.hechas = 0
        self._hilo = threading.Thread(target=self._correr, daemon=True)
        self._hilo.start()
        if esperar:
            self._hilo.join()

    def _log(self, linea: str) -> None:
        with self._lock:
            self.registro.append(linea)
            if linea.startswith("  → "):
                self.hechas += 1

    def _correr(self) -> None:
        try:
            with abrir_store() as store:  # SQLite: la conexión se abre en este hilo
                with self._lock:
                    self.total = sum(1 for e in store.empresas() if e["url_empleos"])
                self._log(f"Revisando vacantes en {self.total} páginas de empleo…")
                self.resultado = rastrear(store, self.fetcher_factory(), log=self._log)
                self._log("Listo.")
        except Exception as exc:  # se muestra en la página en vez de perderse en la consola
            with self._lock:
                self.error = f"La revisión falló: {exc}"
        finally:
            with self._lock:
                self.corriendo = False


def _resumir(nov: dict) -> dict:
    resumen = (nov.get("corrida") or {}).get("resumen") or {}
    return {"nuevas": len(nov.get("nuevas", [])), "encontradas": resumen.get("encontradas", 0),
            "manuales": len(nov.get("manuales", [])), "ya_no_aparecen": len(nov.get("ya_no_aparecen", []))}
