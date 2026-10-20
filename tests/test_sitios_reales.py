"""Fallos vistos en páginas de empleo reales (rastreo del 2026-10-19), cada uno con su prueba."""
from conftest import fixture
from oportunidades import extraer as ex
from oportunidades import servicio
from oportunidades.crawler import decodificar


def test_sin_charset_en_la_cabecera_no_rompe_los_acentos():
    html = '<html><body><a href="/jobs/1">Envía tu CV 📄</a></body></html>'.encode("utf-8")
    assert "Envía tu CV 📄" in decodificar(html, "text/html")
    assert "Envía" in decodificar(html, "")


def test_charset_de_la_cabecera_o_del_meta():
    latin = '<html><head><meta charset="iso-8859-1"></head><body>Logística</body></html>'.encode("latin-1")
    assert "Logística" in decodificar(latin, "text/html")
    assert "Logística" in decodificar("Logística".encode("cp1252"), "text/html; charset=windows-1252")
    assert "Log" in decodificar(b"Log\xedstica sin pistas", "text/html")  # ni utf-8 ni meta: cp1252, sin fallar


def test_enlaces_de_navegacion_y_postulacion_general_no_son_vacantes():
    html = """<html><body><ul class="jobs">
      <li class="job"><a href="https://jobs.ejemplo.do/jobs/1-analista">Analista de Automatización</a></li>
      <li class="job"><a href="https://jobs.ejemplo.do/jobs">Ver vacantes</a></li>
      <li class="job"><a href="https://jobs.ejemplo.do/jobs/2-cv">Envía tu CV 📄</a></li>
      <li class="job"><a href="https://jobs.ejemplo.do/jobs/3">Ver todas las oportunidades</a></li>
      <li class="job"><a href="https://jobs.ejemplo.do/jobs/4">Postulación espontánea</a></li>
    </ul></body></html>"""
    titulos = [v.titulo for v in ex.extraer(html, "https://ejemplo.do/vacantes/").vacantes]
    assert titulos == ["Analista de Automatización"]


def test_categorias_y_enlaces_de_ver_todo_no_son_vacantes():
    html = """<html><body><div class="jobs">
      <a href="/en/careers/engineering">Engineering</a><a href="/en/careers/finance">Finance</a>
      <a href="/en/careers/vacancies">View All Vacancies (Opens in a new tab)</a>
      <a href="/empleos/puestos-disponibles/">Aplica aquí</a>
      <a href="/empleos/puestos-disponibles/%20">Ver prácticas y becas disponibles</a>
      <a href="/en/careers/123-planner">Demand Planner</a>
      <a href="/en/careers/124">Verificador de Calidad</a>
    </div></body></html>"""
    titulos = [v.titulo for v in ex.extraer(html, "https://puerto-ejemplo.do/en/careers").vacantes]
    assert titulos == ["Demand Planner", "Verificador de Calidad"]


def test_postulacion_general_en_un_feed_de_ats():
    rss = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Supervisor de Producción</title><link>https://x.na.teamtailor.com/jobs/1</link></item>
      <item><title>Deja tu curriculum con nosotros - Postúlate en la localidad de tu interés</title>
        <link>https://x.na.teamtailor.com/jobs/2</link></item></channel></rss>"""
    vacs = ex.parse_feed(ex.feed_ats("teamtailor", "x.na"), rss)
    assert [v.titulo for v in vacs] == ["Supervisor de Producción"]


def test_teamtailor_con_region_en_el_subdominio():
    ats = ex.detectar_ats("https://cerveceria-nacional-dominicana.na.teamtailor.com/jobs")
    assert ats.cuenta == "cerveceria-nacional-dominicana.na"
    assert ats.feed == "https://cerveceria-nacional-dominicana.na.teamtailor.com/jobs.rss"
    assert ex.detectar_ats("https://hotelejemplo.teamtailor.com/jobs").cuenta == "hotelejemplo"


def test_portada_casi_vacia_con_muchos_scripts_se_abre_manualmente():
    res = ex.extraer(fixture("successfactors_home.html"), "https://empleos.banco-ejemplo.do/")
    assert res.estado == "abrir manualmente" and "JavaScript" in res.motivo


def test_successfactors_lee_la_pagina_de_busqueda_publica(store, perfil, web_y_fetcher):
    busqueda = "https://empleos.banco-ejemplo.do/search/?q=&sortColumn=referencedate&sortDirection=desc"
    assert ex.busqueda_successfactors(fixture("successfactors_home.html"), "https://empleos.banco-ejemplo.do/") == busqueda
    assert ex.busqueda_successfactors(fixture("careers_plain.html"), "https://x.do/") == ""
    _, fetcher, _ = web_y_fetcher({"https://empleos.banco-ejemplo.do/": fixture("successfactors_home.html"),
                                   busqueda: fixture("successfactors_search.html")})
    store.add_empresa(nombre="Banco Ejemplo", industria="banca", url_empleos="https://empleos.banco-ejemplo.do/")
    servicio.rastrear(store, perfil, fetcher, detalles=False, puntuar_nuevas=False, log=lambda *_: None)
    vacs = sorted(store.vacantes(), key=lambda v: v["titulo"])
    assert [v["titulo"] for v in vacs] == ["Analista de Automatización de Procesos", "Ingeniero de Datos"]
    assert vacs[0]["ubicacion"] == "Santo Domingo, DO"
    assert vacs[0]["url"].startswith("https://empleos.banco-ejemplo.do/job/")
