"""Utilidades de texto: normalizar, slug, URL canónica, idioma, bloqueo de portales de empleo."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Portales de empleo que NO se rastrean (términos de uso, logins, anti-bots).
# Para esas vacantes se usa scripts/pegar.py.
PORTALES_BLOQUEADOS = (
    "linkedin.com", "lnkd.in", "computrabajo.com", "indeed.com", "glassdoor.com",
    "bumeran.com", "monster.com", "ziprecruiter.com", "jooble.org", "talent.com",
    "opcionempleo.com", "trabajando.com", "empleosrd.com", "aldaba.com", "careerjet.com",
    "simplyhired.com", "jobted.com", "neuvoo.com", "infojobs.net",
)

_PARAMS_RASTREO = re.compile(r"^(utm_|gh_src|source|ref|trk|fbclid|gclid|lever-source|lever-origin)", re.I)


def norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9+#./ ]+", " ", text.lower())
    return " ".join(text.split())


def slug(text: str, maxlen: int = 50) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")[:maxlen] or "item"


def host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def es_portal_bloqueado(url: str | None) -> bool:
    if not url:
        return False
    h = host(url)
    if any(h == d or h.endswith("." + d) for d in PORTALES_BLOQUEADOS):
        return True
    # Variantes por país (indeed.com.do, computrabajo.com.do, ...): basta con la marca.
    return any(label in _MARCAS_BLOQUEADAS for label in h.split("."))


_MARCAS_BLOQUEADAS = {"linkedin", "computrabajo", "indeed", "glassdoor", "bumeran", "ziprecruiter",
                      "jooble", "opcionempleo", "infojobs", "careerjet"}


def url_canonica(url: str | None) -> str:
    """Quita parámetros de rastreo, fragmento y barra final, para detectar duplicados."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _PARAMS_RASTREO.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", (parts.hostname or "").lower(), path,
                       urlencode(sorted(query)), ""))


_ES = {"de", "la", "el", "y", "en", "los", "las", "para", "con", "experiencia", "conocimientos",
       "requisitos", "responsabilidades", "empresa", "trabajo", "años", "manejo", "del", "una", "por"}
_EN = {"the", "and", "of", "to", "in", "with", "for", "experience", "requirements", "responsibilities",
       "you", "we", "our", "skills", "years", "team", "will", "is", "are", "a"}


def idioma(text: str) -> str:
    words = re.findall(r"[a-záéíóúñ]+", (text or "").lower())
    es = sum(w in _ES for w in words)
    en = sum(w in _EN for w in words)
    return "en" if en > es else "es"


def limpiar_espacios(text: str | None) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n\n", str(text or ""))).strip()
