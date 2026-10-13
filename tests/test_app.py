import pytest

import app as tablero


@pytest.fixture
def client(store):
    e = store.add_empresa("Banco Ejemplo", "banca", url_empleos="https://b.do/empleos", roles=["Head of Data"])
    store.upsert_vacante("Analista <script>alert(1)</script>", e["id"], descripcion="Python y SQL")
    a = tablero.crear_app()
    a.testing = True
    return a.test_client()


def test_solo_escucha_en_localhost():
    assert tablero.HOST == "127.0.0.1" and tablero.PUERTO == 8765


def test_pagina_y_api(client):
    assert client.get("/").status_code == 200
    r = client.get("/api/resumen").get_json()
    assert r["resumen"]["por_estado"]["Nuevo"] == 1 and "Nuevo" in r["estados"]
    vacs = client.get("/api/vacantes").get_json()
    assert vacs[0]["titulo"].startswith("Analista") and "descripcion" not in vacs[0]
    det = client.get(f"/api/vacantes/{vacs[0]['id']}").get_json()
    assert det["contactos"][0]["rol"] == "Head of Data" and det["historial"][0]["a_estado"] == "Nuevo"
    emps = client.get("/api/empresas").get_json()
    assert emps[0]["vacantes_activas"] == 1 and "linkedin.com/search" in emps[0]["contactos"][0]["linkedin"]


def test_cambiar_estado_nota_y_generar(client):
    vid = client.get("/api/vacantes").get_json()[0]["id"]
    r = client.post(f"/api/vacantes/{vid}/generar", json={})
    assert r.status_code == 400 and "Me interesa" in r.get_json()["error"]
    assert client.post(f"/api/vacantes/{vid}/estado", json={"estado": "Me interesa"}).get_json()["estado"] == "Me interesa"
    assert client.post(f"/api/vacantes/{vid}/estado", json={"estado": "Inventado"}).status_code == 400
    assert client.post(f"/api/vacantes/{vid}/nota", json={"nota": "ok"}).get_json()["nota"] == "ok"
    docs = client.post(f"/api/vacantes/{vid}/generar", json={"tipo": "mensaje"}).get_json()
    assert docs["origen"] == "plantilla" and "Banco Ejemplo" in docs["mensaje"]


def test_rechaza_cambios_que_no_son_json_y_hosts_extranos(client):
    vid = client.get("/api/vacantes").get_json()[0]["id"]
    assert client.post(f"/api/vacantes/{vid}/estado", data={"estado": "Oferta"}).status_code == 415
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/", environ_base={"REMOTE_ADDR": "192.168.1.20"}).status_code == 403


def test_descarga_excel(client):
    r = client.get("/api/excel")
    assert r.status_code == 200 and r.data[:2] == b"PK"


def test_la_interfaz_escapa_el_texto():
    js = (tablero.ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "const esc =" in js and "safeUrl" in js
