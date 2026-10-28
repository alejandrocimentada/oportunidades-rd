"""A quién contactar: las personas que dirigen el área (si el agente las encontró en una fuente
pública) y los cargos a buscar, cada uno con un enlace de LinkedIn.

De las personas solo se guarda lo profesional y público (nombre, cargo, fuente, perfil de LinkedIn);
nunca correos ni teléfonos. Los enlaces se abren con tu propia sesión; nada se visita ni se rastrea.
"""
from __future__ import annotations

from urllib.parse import urlencode

ROLES_SUGERIDOS = {
    "banca": ["Gerente de Innovación", "Head of Data", "Director de Transformación Digital"],
    "telecomunicaciones": ["Director de TI", "Head of Data & Analytics", "Gerente de Innovación"],
    "retail/distribución": ["Gerente de Supply Chain", "Gerente de Analítica", "Gerente de TI"],
    "seguros": ["Gerente de Transformación Digital", "Head of Data", "Director de TI"],
    "zona franca/manufactura": ["Gerente de Supply Chain", "Gerente de Mejora Continua", "IT Manager"],
    "logística": ["Gerente de Operaciones", "IT Manager", "Gerente de Proyectos"],
    "turismo": ["Director de TI", "Gerente de Revenue Management", "Gerente de Innovación"],
    "tecnología/consultoría": ["CTO", "Engineering Manager", "Talent Acquisition"],
    "gobierno-tech": ["Director de Tecnología", "Encargado de Transformación Digital", "Director de Innovación"],
}
ROLES_GENERICOS = ["Talent Acquisition", "Gerente de Recursos Humanos", "Gerente de Innovación"]


def roles_sugeridos(industria: str) -> list[str]:
    return list(ROLES_SUGERIDOS.get(industria, ROLES_GENERICOS))


def url_busqueda_linkedin(empresa: str, rol: str) -> str:
    """Búsqueda de personas en LinkedIn por empresa + cargo (no se visita ni se rastrea)."""
    return "https://www.linkedin.com/search/results/people/?" + urlencode({"keywords": f"{rol} {empresa}"})


def url_linkedin_empresa(empresa: dict) -> str:
    """La página de LinkedIn de la empresa si se conoce; si no, una búsqueda de empresas."""
    return empresa.get("linkedin_empresa") or (
        "https://www.linkedin.com/search/results/companies/?" + urlencode({"keywords": empresa["nombre"]}))


def url_persona_linkedin(empresa: str, nombre: str) -> str:
    """Búsqueda de una persona por nombre + empresa (cuando no se tiene su perfil)."""
    return "https://www.linkedin.com/search/results/people/?" + urlencode({"keywords": f"{nombre} {empresa}"})


def contactos(empresa: dict) -> list[dict]:
    """Primero las personas encontradas (nombre, cargo, fuente), luego los cargos a buscar."""
    personas = [{"nombre": p["nombre"], "rol": p["cargo"], "fuente": p["fuente"],
                 "linkedin": p.get("linkedin") or url_persona_linkedin(empresa["nombre"], p["nombre"])}
                for p in empresa.get("personas") or []]
    roles = empresa.get("roles_contacto") or roles_sugeridos(empresa.get("industria", ""))
    return personas + [{"nombre": "", "rol": r, "fuente": "", "linkedin": url_busqueda_linkedin(empresa["nombre"], r)}
                       for r in roles]
