import pytest

from conftest import fixture
from oportunidades import servicio
from oportunidades.crawler import USER_AGENT, Bloqueado, Prohibido

SITIO = "https://empresa-ejemplo.do"


def test_respeta_robots_txt(web_y_fetcher):
    web, f, _ = web_y_fetcher({f"{SITIO}/robots.txt": fixture("robots_disallow.txt"),
                               f"{SITIO}/empleos": fixture("careers_plain.html")})
    with pytest.raises(Prohibido):
        f.get(f"{SITIO}/empleos")
    assert f"{SITIO}/empleos" not in web.urls()  # nunca se descargó
    assert f.get(f"{SITIO}/nosotros").status == 404  # lo permitido sí se pide


def test_robots_403_prohibe_todo_y_404_permite(web_y_fetcher):
    web, f, _ = web_y_fetcher({"https://a.do/robots.txt": (403, "no"), "https://b.do/x": "ok"})
    assert not f.permitido("https://a.do/empleos")
    assert f.permitido("https://b.do/x")  # robots.txt no existe (404) → permitido


def test_user_agent_claro(web_y_fetcher):
    web, f, _ = web_y_fetcher({f"{SITIO}/empleos": "<html></html>"})
    f.get(f"{SITIO}/empleos")
    ua = web.pedidas[-1][1]["User-Agent"]
    assert ua == USER_AGENT and "OportunidadesRD" in ua and "robots.txt" in ua and "github.com" in ua


def test_maximo_una_peticion_cada_3_segundos_por_sitio(web_y_fetcher):
    web, f, reloj = web_y_fetcher({f"{SITIO}/a": "a", f"{SITIO}/b": "b", f"{SITIO}/c": "c", "https://otro.do/a": "x"})
    for p in ("a", "b", "c"):
        f.get(f"{SITIO}/{p}")
    f.get("https://otro.do/a")
    por_sitio = {}
    for url, t in f.peticiones:
        por_sitio.setdefault(url.split("/")[2], []).append(t)
    for tiempos in por_sitio.values():
        assert all(b - a >= 3.0 for a, b in zip(tiempos, tiempos[1:]))
    assert len(por_sitio[SITIO.split("/")[2]]) == 4  # robots.txt + 3 páginas
    # otro sitio no espera al primero
    assert por_sitio["otro.do"][0] - por_sitio[SITIO.split("/")[2]][-1] < 3.0


def test_cache_24_horas(web_y_fetcher):
    web, f, reloj = web_y_fetcher({f"{SITIO}/empleos": "v1"})
    assert f.get(f"{SITIO}/empleos").texto == "v1"
    web.paginas[f"{SITIO}/empleos"] = (200, "v2")
    r = f.get(f"{SITIO}/empleos")
    assert r.desde_cache and r.texto == "v1"
    assert web.urls().count(f"{SITIO}/empleos") == 1
    reloj.t += 24 * 3600 + 1
    r = f.get(f"{SITIO}/empleos")
    assert not r.desde_cache and r.texto == "v2"


@pytest.mark.parametrize("url", ["https://www.linkedin.com/jobs/view/123", "https://do.computrabajo.com/ofertas",
                                 "https://do.indeed.com/viewjob?jk=1", "https://www.glassdoor.com/Job/x",
                                 "https://indeed.com.do/empleos"])
def test_nunca_rastrea_portales_de_empleo(web_y_fetcher, url):
    web, f, _ = web_y_fetcher({})
    with pytest.raises(Bloqueado):
        f.get(url)
    assert web.pedidas == []


def test_rastreo_completo_marca_robots_y_js_para_revisar(store, perfil, web_y_fetcher):
    store.add_empresa("Prohibida SA", url_empleos=f"{SITIO}/empleos")
    store.add_empresa("SPA SRL", url_empleos="https://spa-ejemplo.do/careers")
    store.add_empresa("Distribuidora Ejemplo", url_empleos="https://distribuidora-ejemplo.do/empleos/")
    store.add_empresa("Telco Ejemplo", url_empleos="https://telco-ejemplo.do/careers")
    web, f, _ = web_y_fetcher({
        f"{SITIO}/robots.txt": fixture("robots_disallow.txt"),
        "https://spa-ejemplo.do/careers": fixture("careers_js_only.html"),
        "https://distribuidora-ejemplo.do/empleos/": fixture("careers_plain.html"),
        "https://distribuidora-ejemplo.do/empleos/101-analista-de-datos?utm_source=web": fixture("vacante_detalle.html"),
        "https://telco-ejemplo.do/careers": fixture("careers_greenhouse.html"),
        "https://boards-api.greenhouse.io/v1/boards/telcoejemplo/jobs?content=true": fixture("greenhouse_jobs.json"),
    })
    nov = servicio.rastrear(store, perfil, f, log=lambda *_: None)
    estados = {e["nombre"]: e["estado_rastreo"] for e in store.empresas()}
    assert estados == {"Prohibida SA": "revisar manualmente", "SPA SRL": "abrir manualmente",
                       "Distribuidora Ejemplo": "ok", "Telco Ejemplo": "ok"}
    assert store.get_empresa("Telco Ejemplo")["ats"] == "greenhouse"
    assert f"{SITIO}/empleos" not in web.urls()
    assert len(nov["nuevas"]) == 5 and all(v["ajuste"] is not None for v in nov["nuevas"])
    assert {m["empresa"] for m in nov["manuales"]} == {"Prohibida SA", "SPA SRL"}
    detalle = store.buscar_duplicado("Distribuidora Ejemplo", "Analista de Datos", "Santo Domingo")
    assert "SQL y Python" in detalle["descripcion"]


def test_novedades_entre_corridas(store, perfil, web_y_fetcher):
    store.add_empresa("Telco Ejemplo", url_empleos="https://telco-ejemplo.do/careers")
    feed = "https://boards-api.greenhouse.io/v1/boards/telcoejemplo/jobs?content=true"
    web, f, reloj = web_y_fetcher({"https://telco-ejemplo.do/careers": fixture("careers_greenhouse.html"),
                                   feed: fixture("greenhouse_jobs.json")}, usar_cache=False)
    primera = servicio.rastrear(store, perfil, f, log=lambda *_: None)
    assert len(primera["nuevas"]) == 2
    segunda = servicio.rastrear(store, perfil, f, log=lambda *_: None)
    assert segunda["nuevas"] == [] and segunda["ya_no_aparecen"] == []
    import json
    data = json.loads(fixture("greenhouse_jobs.json"))
    data["jobs"] = data["jobs"][:1] + [{"id": 4003, "title": "Automation Analyst", "absolute_url":
                                        "https://job-boards.greenhouse.io/telcoejemplo/jobs/4003",
                                        "location": {"name": "Remote"}, "content": "RPA"}]
    web.paginas[feed] = (200, json.dumps(data))
    tercera = servicio.rastrear(store, perfil, f, log=lambda *_: None)
    assert [v["titulo"] for v in tercera["nuevas"]] == ["Automation Analyst"]
    assert [v["titulo"] for v in tercera["ya_no_aparecen"]] == ["Senior Network Engineer"]
    assert store.novedades()["corrida"]["id"] == tercera["corrida"]["id"]
