import pytest

from conftest import fixture
from oportunidades import extraer as ex


def test_html_simple_extrae_titulo_lugar_fecha_y_enlace():
    res = ex.extraer(fixture("careers_plain.html"), "https://distribuidora-ejemplo.do/empleos/")
    assert res.estado == "ok"
    titulos = [v.titulo for v in res.vacantes]
    assert titulos == ["Analista de Datos", "Especialista en Automatización (RPA)", "Ejecutivo de Ventas"]
    a = res.vacantes[0]
    assert a.url == "https://distribuidora-ejemplo.do/empleos/101-analista-de-datos?utm_source=web"
    assert a.ubicacion == "Santo Domingo" and a.fecha == "2026-10-01"
    assert res.vacantes[1].fecha == "2026-09-28"
    # Navegación ("Ver todas", "Iniciar sesión", "Inicio") no se confunde con vacantes
    assert not any("Ver todas" in t or "sesión" in t for t in titulos)


def test_html_con_jsonld():
    res = ex.extraer(fixture("careers_jsonld.html"), "https://seguros-ejemplo.do/empleos")
    assert res.estado == "ok"
    v = res.vacantes[0]
    assert v.titulo == "Ingeniero de IA Aplicada" and v.fecha == "2026-10-05"
    assert "Santo Domingo" in v.ubicacion and "RAG" in v.descripcion and "<p>" not in v.descripcion


def test_texto_de_detalle():
    texto = ex.texto_detalle(fixture("vacante_detalle.html"))
    assert "2 años de experiencia con SQL y Python" in texto
    assert "Inicio" not in texto  # sin navegación


@pytest.mark.parametrize("url,html,nombre,cuenta", [
    ("https://telco-ejemplo.do/careers", fixture("careers_greenhouse.html"), "greenhouse", "telcoejemplo"),
    ("https://logistica-ejemplo.do/empleos", fixture("careers_lever.html"), "lever", "logisticaejemplo"),
    ("https://boards.greenhouse.io/acme", "", "greenhouse", "acme"),
    ("https://job-boards.greenhouse.io/acme", "", "greenhouse", "acme"),
    ("https://jobs.lever.co/acme", "", "lever", "acme"),
    ("https://apply.workable.com/consultora-ejemplo/", "", "workable", "consultora-ejemplo"),
    ("https://careers.smartrecruiters.com/BancoEjemplo", "", "smartrecruiters", "BancoEjemplo"),
    ("https://hotelejemplo.teamtailor.com/jobs", "", "teamtailor", "hotelejemplo"),
    ("https://finanzas.bamboohr.com/careers", "", "bamboohr", "finanzas"),
])
def test_detecta_ats(url, html, nombre, cuenta):
    ats = ex.detectar_ats(url, html)
    assert ats and ats.nombre == nombre and ats.cuenta == cuenta
    assert ats.feed.startswith("https://")


def test_sin_ats_en_pagina_normal():
    assert ex.detectar_ats("https://distribuidora-ejemplo.do/empleos/", fixture("careers_plain.html")) is None


def test_feed_greenhouse():
    vacs = ex.parse_feed(ex.feed_ats("greenhouse", "telcoejemplo"), fixture("greenhouse_jobs.json"))
    assert [v.titulo for v in vacs] == ["AI Integration Engineer", "Senior Network Engineer"]
    assert vacs[0].ubicacion.startswith("Santo Domingo") and vacs[0].fecha == "2026-10-02"
    assert "3+ years" in vacs[0].descripcion and "<p>" not in vacs[0].descripcion


def test_feed_lever():
    vacs = ex.parse_feed(ex.feed_ats("lever", "logisticaejemplo"), fixture("lever_postings.json"))
    v = vacs[0]
    assert v.titulo == "Especialista en Automatización de Procesos" and v.ubicacion == "Santo Domingo"
    assert v.url.endswith("aaa-111") and v.fecha == "2026-10-01"
    assert "Power Automate" in v.descripcion and "2 años de experiencia" in v.descripcion


def test_feeds_workable_smartrecruiters_teamtailor_bamboohr():
    w = ex.parse_feed(ex.feed_ats("workable", "consultora-ejemplo"), fixture("workable.json"))[0]
    assert w.titulo == "Data Engineer" and "remoto" in w.ubicacion and "Airflow" in w.descripcion
    s = ex.parse_feed(ex.feed_ats("smartrecruiters", "BancoEjemplo"), fixture("smartrecruiters.json"))[0]
    assert s.titulo == "Gerente de Analítica" and s.url == "https://jobs.smartrecruiters.com/BancoEjemplo/7440001"
    t = ex.parse_feed(ex.feed_ats("teamtailor", "hotelejemplo"), fixture("teamtailor.rss"))[0]
    assert t.titulo == "Coordinador de Transformación Digital" and t.ubicacion == "Punta Cana"
    assert t.fecha == "2026-10-01" and "IA" in t.descripcion
    b = ex.parse_feed(ex.feed_ats("bamboohr", "finanzas"), fixture("bamboohr.json"))[0]
    assert b.titulo == "Analista de BI" and b.url == "https://finanzas.bamboohr.com/careers/21"


def test_pagina_solo_javascript_se_abre_manualmente():
    res = ex.extraer(fixture("careers_js_only.html"), "https://spa-ejemplo.do/careers")
    assert res.estado == "abrir manualmente" and "JavaScript" in res.motivo
    assert res.vacantes == []


def test_pagina_con_login_se_abre_manualmente():
    res = ex.extraer(fixture("login.html"), "https://portal-ejemplo.do/candidatos")
    assert res.estado == "abrir manualmente" and "sesión" in res.motivo


def test_redireccion_a_login_y_errores_http():
    res = ex.extraer("<html></html>", "https://x.do/empleos", 200, "https://x.do/login?next=/empleos")
    assert res.estado == "abrir manualmente"
    assert ex.extraer("", "https://x.do/empleos", 403).estado == "abrir manualmente"


def test_pagina_sin_vacantes():
    res = ex.extraer("<html><body><h1>Empleos</h1><p>No tenemos vacantes abiertas por ahora, pero puedes "
                     "enviarnos tu CV a nuestra área de talento humano. Gracias por tu interés en formar "
                     "parte de nuestro equipo de trabajo en toda la República Dominicana.</p></body></html>",
                     "https://x.do/empleos")
    assert res.estado == "sin vacantes"
