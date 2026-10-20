import pytest

import app as tablero
from conftest import empresa


@pytest.fixture
def client(store):
    e = empresa(store, "Banco <script>alert(1)</script>", url_empleos="https://b.do/empleos",
                roles_contacto=["Head of Data"], equipos=["Datos y analítica"],
                roles=[{"rol": "BI Analyst", "razon": "Tableros en Tableau."}])
    store.upsert_vacante("Analista de Datos", e["id"], descripcion="Python y SQL")
    a = tablero.crear_app()
    a.testing = True
    return a.test_client()


def test_solo_escucha_en_localhost():
    assert tablero.HOST == "127.0.0.1" and tablero.PUERTO == 8765


def test_pagina_y_api(client):
    assert client.get("/").status_code == 200
    r = client.get("/api/resumen").get_json()
    assert r["resumen"]["por_estado"]["Descubierta"] == 1 and "Descubierta" in r["estados"]
    emps = client.get("/api/empresas").get_json()
    assert emps[0]["vacantes"] == "hay vacantes" and "linkedin.com/search" in emps[0]["contactos"][0]["linkedin"]
    det = client.get(f"/api/empresas/{emps[0]['id']}").get_json()
    assert det["roles"][0]["rol"] == "BI Analyst" and det["historial"][0]["a_estado"] == "Descubierta"
    assert det["lista_vacantes"][0]["titulo"] == "Analista de Datos" and "descripcion" not in det["lista_vacantes"][0]
    vacs = client.get("/api/vacantes").get_json()
    assert vacs[0]["titulo"] == "Analista de Datos" and "descripcion" not in vacs[0] and "ajuste" not in vacs[0]


def test_cambiar_estado_nota_y_generar(client):
    eid = client.get("/api/empresas").get_json()[0]["id"]
    r = client.post(f"/api/empresas/{eid}/generar", json={})
    assert r.status_code == 400 and "Me interesa" in r.get_json()["error"]
    assert client.post(f"/api/empresas/{eid}/estado", json={"estado": "Me interesa"}).get_json()["estado"] == "Me interesa"
    assert client.post(f"/api/empresas/{eid}/estado", json={"estado": "Inventado"}).status_code == 400
    assert client.post(f"/api/empresas/{eid}/nota", json={"nota": "ok"}).get_json()["nota"] == "ok"
    docs = client.post(f"/api/empresas/{eid}/generar", json={"tipo": "mensaje", "rol": "BI Analyst"}).get_json()
    assert docs["origen"] == "plantilla" and "BI Analyst" in docs["mensaje"] and "Datos y analítica" in docs["mensaje"]


def test_rechaza_cambios_que_no_son_json_y_hosts_extranos(client):
    eid = client.get("/api/empresas").get_json()[0]["id"]
    assert client.post(f"/api/empresas/{eid}/estado", data={"estado": "Oferta"}).status_code == 415
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/", environ_base={"REMOTE_ADDR": "192.168.1.20"}).status_code == 403


def test_descarga_excel(client):
    r = client.get("/api/excel")
    assert r.status_code == 200 and r.data[:2] == b"PK"


def test_la_interfaz_escapa_el_texto_y_no_tiene_puntuacion():
    js = (tablero.ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "const esc =" in js and "safeUrl" in js
    assert "ajuste" not in js and "puntu" not in js


def test_perfil_desde_la_pagina(client):
    r = client.get("/api/perfil").get_json()
    assert r["existe"] is False and r["perfil"]["ia"]["proveedor"] == "agente"
    body = {"nombre": "Ana", "roles_objetivo": ["AI Engineer", "Automation"], "anos_experiencia": "3",
            "preferencias": {"modalidad": "remoto", "salario_minimo_dop": "90000", "salario_flexible_startups": True,
                             "inventado": "x"},
            "industrias": ["banca"], "ia": {"proveedor": "agente"}, "ruta_secreta": "no"}
    p = client.post("/api/perfil", json=body).get_json()["perfil"]
    assert p["nombre"] == "Ana" and p["roles_objetivo"] == ["AI Engineer", "Automation"] and p["anos_experiencia"] == 3
    assert p["preferencias"]["salario_flexible_startups"] is True and "inventado" not in p["preferencias"]
    assert "ruta_secreta" not in p and client.get("/api/perfil").get_json()["existe"] is True
    assert client.post("/api/perfil", json={"preferencias": {"modalidad": "a veces"}}).status_code == 400


def test_revisar_vacantes_desde_la_pagina(store, web_y_fetcher):
    from conftest import fixture
    from oportunidades.busqueda import Busqueda
    empresa(store, "Empresa Ejemplo", url_empleos="https://empresa-ejemplo.do/empleos")
    _, fetcher, _ = web_y_fetcher({"https://empresa-ejemplo.do/empleos": fixture("careers_plain.html")})
    busqueda = Busqueda(lambda: fetcher)
    c = tablero.crear_app(busqueda=busqueda).test_client()
    assert c.post("/api/buscar", json={}).status_code == 400  # sin perfil, no revisa
    c.post("/api/perfil", json={"roles_objetivo": ["Analista de datos"]})
    assert c.post("/api/buscar", json={}).status_code == 200
    busqueda._hilo.join(10)
    e = c.get("/api/buscar").get_json()
    assert not e["corriendo"] and not e["error"] and e["resultado"]["encontradas"] >= 1
    assert e["hechas"] == e["total"] == 1 and e["registro"][-1] == "Listo."
    assert c.get("/api/empresas").get_json()[0]["vacantes"] == "hay vacantes"
