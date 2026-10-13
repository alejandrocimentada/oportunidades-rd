import datetime as dt

import pytest

from oportunidades import contactos
from oportunidades.db import ESTADOS, DatosError, columnas


def test_dedupe_por_url_canonica(store):
    e = store.add_empresa("Banco Ejemplo", "banca")
    v1, nueva1 = store.upsert_vacante("Analista de Datos", e["id"], url="https://b.do/empleos/1?utm_source=x")
    v2, nueva2 = store.upsert_vacante("Analista de datos ", e["id"], url="https://b.do/empleos/1/#aplicar")
    assert nueva1 and not nueva2 and v1["id"] == v2["id"]
    assert len(store.vacantes()) == 1


def test_dedupe_por_empresa_titulo_y_lugar(store):
    v1, _ = store.upsert_vacante("Ingeniero de IA", empresa_nombre="Seguros Ejemplo", ubicacion="Santo Domingo")
    v2, nueva = store.upsert_vacante("INGENIERO DE IA", empresa_nombre="seguros ejemplo", ubicacion="Santo Domingo",
                                     descripcion="Texto más completo de la vacante")
    assert not nueva and v2["id"] == v1["id"] and v2["descripcion"].startswith("Texto más completo")
    _, otra = store.upsert_vacante("Ingeniero de IA", empresa_nombre="Seguros Ejemplo", ubicacion="Santiago")
    assert otra


def test_empresa_duplicada_se_actualiza(store):
    a = store.add_empresa("Telco Ejemplo", "telecomunicaciones", interes=60)
    b = store.add_empresa("TELCO  ejemplo", interes=80, url_empleos="https://t.do/empleos")
    assert a["id"] == b["id"] and b["interes"] == 80 and b["industria"] == "telecomunicaciones"
    assert b["estado_rastreo"] == "pendiente"


def test_flujo_de_estados_con_historial_y_fechas(store):
    v, _ = store.upsert_vacante("Analista de BI", empresa_nombre="X")
    assert v["estado"] == "Nuevo"
    for estado in ["Me interesa", "Aplicado", "Contacté", "Entrevista", "Oferta"]:
        v = store.cambiar_estado(v["id"], estado, nota=f"nota {estado}")
        assert v["estado"] == estado
    h = store.historial(v["id"])
    assert [x["a_estado"] for x in h] == ["Nuevo", "Me interesa", "Aplicado", "Contacté", "Entrevista", "Oferta"]
    assert [x["de_estado"] for x in h][1:] == ["Nuevo", "Me interesa", "Aplicado", "Contacté", "Entrevista"]
    assert all(dt.datetime.fromisoformat(x["fecha"]) for x in h)
    assert h[2]["nota"] == "nota Aplicado"


def test_mismo_estado_no_duplica_historial_y_estado_invalido(store):
    v, _ = store.upsert_vacante("Analista", empresa_nombre="X")
    store.cambiar_estado(v["id"], "Nuevo")
    assert len(store.historial(v["id"])) == 1
    with pytest.raises(DatosError):
        store.cambiar_estado(v["id"], "Contratado")


def test_seguimiento_se_agenda_al_aplicar_y_se_limpia_al_cerrar(store):
    v, _ = store.upsert_vacante("Analista", empresa_nombre="X")
    v = store.cambiar_estado(v["id"], "Aplicado")
    assert v["seguimiento"] == (dt.date.today() + dt.timedelta(days=7)).isoformat()
    r = store.resumen()
    assert r["aplicadas_semana"] == 1 and r["seguimientos"][0]["id"] == v["id"]
    v = store.cambiar_estado(v["id"], "Descartado")
    assert v["seguimiento"] == "" and store.resumen()["seguimientos"] == []
    with pytest.raises(DatosError):
        store.set_seguimiento(v["id"], "20-10-2026")


def test_resumen_cuenta_por_estado(store):
    for i in range(3):
        store.upsert_vacante(f"Puesto {i}", empresa_nombre="X")
    store.cambiar_estado(1, "Me interesa")
    r = store.resumen()
    assert set(r["por_estado"]) == set(ESTADOS)
    assert r["por_estado"]["Nuevo"] == 2 and r["por_estado"]["Me interesa"] == 1 and r["total_vacantes"] == 3


def test_nota(store):
    v, _ = store.upsert_vacante("Analista", empresa_nombre="X")
    assert store.set_nota(v["id"], "Llamar el lunes")["nota"] == "Llamar el lunes"


# -- contactos: solo roles, nunca datos personales ----------------------------------------
def test_no_existen_campos_de_datos_personales_para_contactos(store):
    prohibidos = {"email", "correo", "telefono", "phone", "contacto_nombre", "persona", "nombre_contacto",
                  "linkedin_perfil", "celular", "whatsapp", "direccion"}
    for tabla in ("empresas", "vacantes", "historial", "corridas"):
        cols = set(columnas(store, tabla))
        assert not cols & prohibidos, (tabla, cols & prohibidos)
    assert "roles_contacto" in columnas(store, "empresas")


@pytest.mark.parametrize("rol", ["juan.perez@banco.do", "809-555-1234", "+1 809 555 1234",
                                 "https://www.linkedin.com/in/juan-perez", "www.ejemplo.com"])
def test_rechaza_datos_personales_como_rol(store, rol):
    with pytest.raises(DatosError):
        store.add_empresa("Banco Ejemplo", "banca", roles=[rol])


def test_contactos_son_roles_con_busqueda_de_linkedin(store):
    e = store.add_empresa("Banco Ejemplo", "banca", roles=["Head of Data", "Gerente de Innovación"])
    cts = contactos.contactos(e)
    assert [c["rol"] for c in cts] == ["Head of Data", "Gerente de Innovación"]
    assert set(cts[0]) == {"rol", "linkedin"}
    assert cts[0]["linkedin"] == ("https://www.linkedin.com/search/results/people/?keywords="
                                  "Head+of+Data+Banco+Ejemplo")
    sin_roles = store.add_empresa("Telco Ejemplo", "telecomunicaciones")
    assert len(contactos.contactos(sin_roles)) == 3  # sugeridos por industria


def test_no_acepta_portales_como_pagina_de_empleos(store):
    with pytest.raises(DatosError):
        store.add_empresa("X", url_empleos="https://www.linkedin.com/company/x/jobs")
    with pytest.raises(DatosError):
        store.add_empresa("Y", url_empleos="https://do.computrabajo.com/empresas/ofertas-de-trabajo-de-y")
    e = store.add_empresa("Z")
    assert e["estado_rastreo"] == "sin página"
