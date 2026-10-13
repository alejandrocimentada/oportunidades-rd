"""Extraer vacantes de páginas de empleo.

1. Detecta sistemas de reclutamiento (ATS) públicos comunes y usa su feed/JSON público:
   Greenhouse, Lever, Workable, SmartRecruiters, Teamtailor, BambooHR.
2. Si no hay ATS, lee datos estructurados (schema.org JobPosting en JSON-LD).
3. Si no, busca enlaces que parecen vacantes en el HTML.
4. Si la página necesita JavaScript o login → "abrir manualmente".
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .texto import limpiar_espacios


@dataclass
class Vacante:
    titulo: str
    url: str = ""
    ubicacion: str = ""
    fecha: str = ""
    descripcion: str = ""


@dataclass
class ATS:
    nombre: str
    cuenta: str
    feed: str           # URL del feed/JSON público
    pagina: str = ""    # página pública para personas


@dataclass
class Resultado:
    vacantes: list[Vacante] = field(default_factory=list)
    estado: str = "ok"          # ok | sin vacantes | abrir manualmente
    motivo: str = ""
    ats: str = ""


# -- detección de ATS ----------------------------------------------------------------------
_PATRONES_ATS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)", re.I)),
    ("lever", re.compile(r"api\.(?:eu\.)?lever\.co/v0/postings/([A-Za-z0-9_.-]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/(?:api/v\d/widget/accounts/)?([A-Za-z0-9_-]+)", re.I)),
    ("workable", re.compile(r"([A-Za-z0-9_-]+)\.workable\.com", re.I)),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)", re.I)),
    ("teamtailor", re.compile(r"([A-Za-z0-9_-]+)\.teamtailor\.com", re.I)),
    ("bamboohr", re.compile(r"([A-Za-z0-9_-]+)\.bamboohr\.com", re.I)),
]
_CUENTAS_INVALIDAS = {"www", "api", "apply", "jobs", "careers", "app", "assets", "embed", "cdn", "static",
                      "scripts", "boards", "job-boards", "v0", "v1", "resources"}


def feed_ats(nombre: str, cuenta: str) -> ATS:
    if nombre == "greenhouse":
        return ATS(nombre, cuenta, f"https://boards-api.greenhouse.io/v1/boards/{cuenta}/jobs?content=true",
                   f"https://job-boards.greenhouse.io/{cuenta}")
    if nombre == "lever":
        return ATS(nombre, cuenta, f"https://api.lever.co/v0/postings/{cuenta}?mode=json",
                   f"https://jobs.lever.co/{cuenta}")
    if nombre == "workable":
        return ATS(nombre, cuenta, f"https://apply.workable.com/api/v1/widget/accounts/{cuenta}?details=true",
                   f"https://apply.workable.com/{cuenta}/")
    if nombre == "smartrecruiters":
        return ATS(nombre, cuenta, f"https://api.smartrecruiters.com/v1/companies/{cuenta}/postings",
                   f"https://jobs.smartrecruiters.com/{cuenta}")
    if nombre == "teamtailor":
        return ATS(nombre, cuenta, f"https://{cuenta}.teamtailor.com/jobs.rss",
                   f"https://{cuenta}.teamtailor.com/jobs")
    if nombre == "bamboohr":
        return ATS(nombre, cuenta, f"https://{cuenta}.bamboohr.com/careers/list",
                   f"https://{cuenta}.bamboohr.com/careers")
    raise ValueError(nombre)


def detectar_ats(url: str, html: str = "") -> ATS | None:
    """Busca un ATS en la URL de la página de empleos o en enlaces/iframes/scripts de su HTML."""
    candidatos = [url]
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["a", "iframe", "script", "link", "form"]):
            for attr in ("href", "src", "action", "data-src"):
                if tag.get(attr):
                    candidatos.append(tag[attr])
        candidatos.append(html)  # p. ej. URLs dentro de scripts en línea
    for texto in candidatos:
        for nombre, patron in _PATRONES_ATS:
            m = patron.search(texto or "")
            if m and m.group(1).lower() not in _CUENTAS_INVALIDAS:
                return feed_ats(nombre, m.group(1))
    return None


# -- feeds de ATS --------------------------------------------------------------------------
def _texto_html(fragmento: str) -> str:
    if not fragmento:
        return ""
    return limpiar_espacios(BeautifulSoup(htmllib.unescape(fragmento), "html.parser").get_text("\n"))


def _fecha(valor) -> str:
    if valor in (None, ""):
        return ""
    if isinstance(valor, (int, float)):  # milisegundos (Lever)
        return dt.datetime.fromtimestamp(valor / 1000, dt.timezone.utc).date().isoformat()
    texto = str(valor)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", texto)
    if m:
        return m.group(1)
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(texto).date().isoformat()
    except (TypeError, ValueError):
        return ""


def parse_greenhouse(texto: str) -> list[Vacante]:
    data = json.loads(texto)
    return [Vacante(titulo=j.get("title", ""), url=j.get("absolute_url", ""),
                    ubicacion=(j.get("location") or {}).get("name", ""),
                    fecha=_fecha(j.get("first_published") or j.get("updated_at")),
                    descripcion=_texto_html(j.get("content", "")))
            for j in data.get("jobs", [])]


def parse_lever(texto: str) -> list[Vacante]:
    data = json.loads(texto)
    out = []
    for j in data if isinstance(data, list) else []:
        cats = j.get("categories") or {}
        desc = j.get("descriptionPlain") or _texto_html(j.get("description", ""))
        for bloque in j.get("lists") or []:
            desc += "\n\n" + bloque.get("text", "") + "\n" + _texto_html(bloque.get("content", ""))
        out.append(Vacante(titulo=j.get("text", ""), url=j.get("hostedUrl", ""),
                           ubicacion=cats.get("location", "") or ", ".join(cats.get("allLocations") or []),
                           fecha=_fecha(j.get("createdAt")), descripcion=limpiar_espacios(desc)))
    return out


def parse_workable(texto: str) -> list[Vacante]:
    data = json.loads(texto)
    out = []
    for j in data.get("jobs", []):
        lugar = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        if j.get("telecommuting"):
            lugar = (lugar + " · remoto").strip(" ·")
        out.append(Vacante(titulo=j.get("title", ""), url=j.get("url") or j.get("shortlink", ""),
                           ubicacion=lugar, fecha=_fecha(j.get("published_on") or j.get("created_at")),
                           descripcion=_texto_html(j.get("description", ""))))
    return out


def parse_smartrecruiters(texto: str, cuenta: str = "") -> list[Vacante]:
    data = json.loads(texto)
    out = []
    for j in data.get("content", []):
        loc = j.get("location") or {}
        lugar = ", ".join(x for x in (loc.get("city"), loc.get("country", "").upper()) if x)
        if loc.get("remote"):
            lugar = (lugar + " · remoto").strip(" ·")
        empresa = (j.get("company") or {}).get("identifier") or cuenta
        url = j.get("postingUrl") or (f"https://jobs.smartrecruiters.com/{empresa}/{j.get('id')}" if j.get("id") else "")
        out.append(Vacante(titulo=j.get("name", ""), url=url, ubicacion=lugar,
                           fecha=_fecha(j.get("releasedDate"))))
    return out


def parse_teamtailor(texto: str) -> list[Vacante]:
    root = ET.fromstring(texto.encode("utf-8") if isinstance(texto, str) else texto)
    out = []
    for item in root.iter("item"):
        lugar = ""
        for child in item:
            if child.tag.endswith("location") or child.tag.endswith("city"):
                lugar = lugar or "".join(child.itertext()).strip()
        out.append(Vacante(titulo=(item.findtext("title") or "").strip(), url=(item.findtext("link") or "").strip(),
                           ubicacion=lugar, fecha=_fecha(item.findtext("pubDate")),
                           descripcion=_texto_html(item.findtext("description") or "")))
    return out


def parse_bamboohr(texto: str, cuenta: str = "") -> list[Vacante]:
    data = json.loads(texto)
    out = []
    for j in data.get("result", []):
        loc = j.get("location") or {}
        lugar = ", ".join(x for x in (loc.get("city"), loc.get("state")) if x)
        if j.get("isRemote"):
            lugar = (lugar + " · remoto").strip(" ·")
        out.append(Vacante(titulo=j.get("jobOpeningName", ""),
                           url=f"https://{cuenta}.bamboohr.com/careers/{j.get('id')}" if cuenta else "",
                           ubicacion=lugar))
    return out


def parse_feed(ats: ATS, texto: str) -> list[Vacante]:
    parser = {
        "greenhouse": parse_greenhouse, "lever": parse_lever, "workable": parse_workable,
        "teamtailor": parse_teamtailor,
        "smartrecruiters": lambda t: parse_smartrecruiters(t, ats.cuenta),
        "bamboohr": lambda t: parse_bamboohr(t, ats.cuenta),
    }[ats.nombre]
    return [v for v in parser(texto) if v.titulo]


# -- páginas que no se pueden leer ---------------------------------------------------------
_SENALES_LOGIN = re.compile(r"(inicia(r)? sesi[oó]n|sign in to (view|continue)|log ?in to (view|continue)|"
                            r"iniciar sesión para ver|please log ?in)", re.I)
_SENALES_ANTIBOT = re.compile(r"(cf-chl|challenge-platform|captcha|verify you are human|"
                              r"comprueba que eres humano|access denied|attention required)", re.I)
_SENALES_JS = re.compile(r"(enable javascript|habilita javascript|activa javascript|requires javascript|"
                         r"you need to enable javascript|necesitas javascript)", re.I)


def diagnosticar(html: str, status: int = 200, url_final: str = "") -> str:
    """'' si la página se puede leer; si no, el motivo para abrirla manualmente."""
    if status in (401, 403):
        return "La página pide permiso o bloquea visitas automáticas (código %d)." % status
    if status == 429:
        return "El sitio pidió bajar el ritmo (código 429)."
    if status >= 400:
        return f"La página respondió con error {status}."
    if url_final and re.search(r"/(login|signin|sign-in|iniciar-sesion|auth)\b", urlsplit(url_final).path, re.I):
        return "La página redirige a un inicio de sesión."
    soup = BeautifulSoup(html or "", "html.parser")
    if soup.find("input", attrs={"type": "password"}) or (_SENALES_LOGIN.search(soup.get_text(" ")) and
                                                         len(soup.get_text(" ").split()) < 400):
        return "La página pide iniciar sesión."
    if _SENALES_ANTIBOT.search(html or "") and len(soup.get_text(" ").split()) < 300:
        return "La página tiene una protección anti-bots (no se intenta saltar)."
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    visible = soup.get_text(" ").split()
    if len(visible) < 40 and (_SENALES_JS.search(html or "") or
                              re.search(r'id=["\'](root|app|__next|__nuxt)["\']', html or "")):
        return "La página necesita JavaScript para mostrar las vacantes."
    return ""


# -- HTML genérico -------------------------------------------------------------------------
_PALABRAS_VACANTE = re.compile(
    r"(/jobs?/|/vacantes?/|/empleos?/|/careers?/.+|/carreras?/.+|/oportunidades?/.+|/ofertas?/|"
    r"/posiciones?/|/positions?/|/puestos?/|/openings?/|/trabaja-con-nosotros/.+|job_?id=|vacante=|"
    r"/requisition)", re.I)
_CLASES_VACANTE = re.compile(r"(job|vacan|posting|position|opening|oferta|empleo|career|puesto|cargo)", re.I)
_CLASES_LUGAR = re.compile(r"(location|ubicaci|lugar|ciudad|city|sede|localidad)", re.I)
_CLASES_FECHA = re.compile(r"(date|fecha|posted|publicad)", re.I)
_TITULOS_NAVEGACION = re.compile(
    r"^(ver (m[aá]s|todas?|detalles?)|aplicar|apply( now)?|leer m[aá]s|more|see all|view all|empleos?|"
    r"vacantes?|careers?|jobs?|carreras?|inicio|home|trabaja con nosotros|[0-9]+|siguiente|anterior|next|"
    r"previous|«|»|→|←)$", re.I)


def _jsonld(soup: BeautifulSoup, base: str) -> list[Vacante]:
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict) or "JobPosting" not in str(item.get("@type")):
                continue
            loc = item.get("jobLocation") or {}
            loc = loc[0] if isinstance(loc, list) and loc else loc
            addr = (loc or {}).get("address") or {} if isinstance(loc, dict) else {}
            lugar = ", ".join(x for x in (addr.get("addressLocality"), addr.get("addressCountry")
                                          if isinstance(addr.get("addressCountry"), str) else "") if x) \
                if isinstance(addr, dict) else ""
            if str(item.get("jobLocationType", "")).upper() == "TELECOMMUTE":
                lugar = (lugar + " · remoto").strip(" ·")
            out.append(Vacante(titulo=limpiar_espacios(item.get("title", "")),
                               url=urljoin(base, item.get("url", "") or ""), ubicacion=lugar,
                               fecha=_fecha(item.get("datePosted")),
                               descripcion=_texto_html(item.get("description", ""))))
    return [v for v in out if v.titulo]


def _contenedor(a):
    """El elemento 'tarjeta' que rodea un enlace de vacante (li, article, tr, div con clase de vacante)."""
    nodo = a
    for _ in range(5):
        nodo = nodo.parent
        if nodo is None or nodo.name in ("body", "html"):
            return a.parent
        if nodo.name in ("li", "article", "tr") or _CLASES_VACANTE.search(" ".join(nodo.get("class", []))):
            return nodo
    return a.parent


def _texto_por_clase(nodo, patron) -> str:
    if nodo is None:
        return ""
    for el in nodo.find_all(True):
        clases = " ".join(el.get("class", [])) + " " + (el.get("itemprop") or "")
        if patron.search(clases):
            if el.name == "time" and el.get("datetime"):
                return el["datetime"]
            return limpiar_espacios(el.get_text(" "))
    t = nodo.find("time")
    if patron is _CLASES_FECHA and t is not None:
        return t.get("datetime") or t.get_text(" ")
    return ""


def extraer_html(html: str, base_url: str) -> list[Vacante]:
    soup = BeautifulSoup(html or "", "html.parser")
    vacs = _jsonld(soup, base_url)
    if vacs:
        return vacs
    for t in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        t.decompose()
    vistos, out = set(), []
    base_host = urlsplit(base_url).hostname or ""
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if urlsplit(href).scheme not in ("http", "https") or href.rstrip("/") == base_url.rstrip("/"):
            continue
        cont = _contenedor(a)
        clases = " ".join(a.get("class", [])) + " " + " ".join((cont.get("class", []) if cont else []))
        if not (_PALABRAS_VACANTE.search(urlsplit(href).path + "?" + urlsplit(href).query)
                or _CLASES_VACANTE.search(clases)):
            continue
        h = a.find(["h2", "h3", "h4", "strong"]) or (cont.find(["h2", "h3", "h4"]) if cont else None)
        titulo = limpiar_espacios((h or a).get_text(" "))
        if (not titulo or len(titulo) < 4 or len(titulo) > 140 or _TITULOS_NAVEGACION.match(titulo)
                or href in vistos):
            continue
        if urlsplit(href).hostname and urlsplit(href).hostname != base_host and not _PALABRAS_VACANTE.search(href):
            continue
        vistos.add(href)
        out.append(Vacante(titulo=titulo, url=href, ubicacion=_texto_por_clase(cont, _CLASES_LUGAR),
                           fecha=_fecha(_texto_por_clase(cont, _CLASES_FECHA)) or
                           _texto_por_clase(cont, _CLASES_FECHA)))
    return out


def texto_detalle(html: str) -> str:
    """Texto principal de la página de una vacante (para la descripción)."""
    soup = BeautifulSoup(html or "", "html.parser")
    for v in _jsonld(soup, ""):
        if v.descripcion:
            return v.descripcion
    for t in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.find(class_=re.compile("(job|vacan|description|descripci)", re.I)) or soup.body or soup
    return limpiar_espacios(main.get_text("\n"))[:12000]


def extraer(html: str, url: str, status: int = 200, url_final: str = "") -> Resultado:
    redirige_a_login = bool(url_final and re.search(r"/(login|signin|sign-in|iniciar-sesion|auth)\b",
                                                     urlsplit(url_final).path, re.I))
    if status >= 400 or redirige_a_login:
        return Resultado(estado="abrir manualmente", motivo=diagnosticar(html, status, url_final))
    vacs = extraer_html(html, url_final or url)
    if vacs:
        return Resultado(vacantes=vacs)
    # Sin vacantes: ¿la página está vacía de verdad o necesita JavaScript / login?
    motivo = diagnosticar(html, status, url_final)
    if motivo:
        return Resultado(estado="abrir manualmente", motivo=motivo)
    return Resultado(estado="sin vacantes", motivo="No se encontraron vacantes en la página.")
