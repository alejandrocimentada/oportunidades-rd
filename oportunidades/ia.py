"""Proveedor de IA para redactar el mensaje y la carta: Claude (Anthropic) u OpenAI, con tu propia clave.

- ia.proveedor en el perfil: "claude", "openai", "agente" o "ninguno".
  - "agente": el agente que ejecuta SKILL.md (p. ej. Claude Code) investiga empresas y redacta él mismo;
    los scripts no llaman a ninguna API.
  - "ninguno": solo plantillas básicas.
- Claves: ANTHROPIC_API_KEY (Claude) u OPENAI_API_KEY (OpenAI), en variables de entorno.
- Tus datos (perfil + datos de la empresa) solo se envían al proveedor elegido.
"""
from __future__ import annotations

import os

MODELOS_POR_DEFECTO = {"claude": "claude-sonnet-5-5", "openai": "gpt-5"}
VARIABLES = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


class IAError(RuntimeError):
    """La IA no está disponible o falló."""


def proveedor(perfil: dict) -> str:
    return (perfil.get("ia") or {}).get("proveedor", "agente")


def disponible(perfil: dict) -> bool:
    p = proveedor(perfil)
    return p in VARIABLES and bool(os.environ.get(VARIABLES[p]))


def _llamar_claude(sistema: str, usuario: str, modelo: str) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise IAError("Falta el paquete 'anthropic': pip install anthropic") from exc
    client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=modelo, max_tokens=16000, system=sistema,
        messages=[{"role": "user", "content": usuario}],
        # Si el modelo declina la petición, la API la reintenta con otro modelo de Claude.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    )
    if resp.stop_reason == "refusal":
        raise IAError("Claude declinó la petición.")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _llamar_openai(sistema: str, usuario: str, modelo: str) -> str:
    try:
        import openai
    except ImportError as exc:
        raise IAError("Falta el paquete 'openai': pip install openai") from exc
    client = openai.OpenAI()  # lee OPENAI_API_KEY
    resp = client.chat.completions.create(
        model=modelo, messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}])
    return resp.choices[0].message.content or ""


def completar(perfil: dict, sistema: str, usuario: str, llamadas: dict | None = None) -> str:
    """Envía el texto SOLO al proveedor elegido en el perfil. `llamadas` permite inyectar fakes en pruebas."""
    p = proveedor(perfil)
    if p not in VARIABLES:
        raise IAError(f"El proveedor '{p}' no usa API (el agente o las plantillas hacen el trabajo).")
    if not os.environ.get(VARIABLES[p]):
        raise IAError(f"Falta la variable de entorno {VARIABLES[p]} con tu clave de {p}.")
    modelo = (perfil.get("ia") or {}).get("modelo") or MODELOS_POR_DEFECTO[p]
    funcs = llamadas or {"claude": _llamar_claude, "openai": _llamar_openai}
    try:
        return funcs[p](sistema, usuario, modelo)
    except IAError:
        raise
    except Exception as exc:  # errores de red, clave inválida, límites…
        raise IAError(f"Error al llamar a {p}: {exc}") from exc


def perfil_para_ia(perfil: dict) -> dict:
    """Solo lo necesario para redactar (sin rutas ni configuración)."""
    claves = ["nombre", "titular", "roles_objetivo", "habilidades", "experiencia", "anos_experiencia",
              "idiomas", "ubicacion", "preferencias", "enlaces", "industrias"]
    return {k: perfil.get(k) for k in claves}
