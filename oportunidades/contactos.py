"""A quién contactar: solo ROLES y enlaces de búsqueda de LinkedIn.

Nunca se guardan nombres, correos, teléfonos ni perfiles de personas. El enlace abre una
búsqueda en LinkedIn (con tu propia sesión) y tú decides a quién escribir.
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


def contactos(empresa: dict) -> list[dict]:
    roles = empresa.get("roles_contacto") or roles_sugeridos(empresa.get("industria", ""))
    return [{"rol": r, "linkedin": url_busqueda_linkedin(empresa["nombre"], r)} for r in roles]
