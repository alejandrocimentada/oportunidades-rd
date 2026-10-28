import datetime as dt
import sqlite3

import pytest

from conftest import empresa
from oportunidades import contactos
from oportunidades.db import ESTADOS, DatosError, Store, columnas

FUENTE = [{"titulo": "Centro de servicios en Santo Domingo", "url": "https://empresa.example/rd"}]


# -- empresas: presencia verificada y datos del encaje ------------------------------------
def test_sin_fuente_de_presencia_en_rd_no_se_agrega(store):
    for fuentes in (None, [], [{"titulo": "dice que está en RD"}], ["no es un enlace"]):
        data = {"nombre": "Empresa Sin Fuente"}
        if fuentes is not None:
            data["fuentes_presencia"] = fuentes
        with pytest.raises(DatosError):
            store.guardar_empresa(data)
    assert store.empresas() == []


def test_guarda_equipos_roles_evidencia_razones_alertas_y_como_postular(store):
    e, nueva = store.guardar_empresa({
        "nombre": "Servicios Globales", "tipo": "multinacional", "industria": "tecnología/consultoría",
        "presencia_rd": "Centro de servicios compartidos en Santo Domingo.",
        "fuentes_presencia": FUENTE + ["https://zonafranca.example/directorio/servicios-globales"],
        "equipos": ["Supply chain", "BI y analítica"],
        "roles": [{"rol": "BI Analyst", "razon": "Tableros en Tableau."}, "SAP Functional Analyst: usuario de SAP"],
        "evidencia": [{"texto": "Vacante pasada de BI Analyst en SD", "url": "https://empresa.example/jobs/1"}],
        "razones": ["a", "b", "c", "d"], "alertas": ["Pide inglés avanzado."],
        "url_empleos": "https://empresa.example/careers", "portal_rd": "https://empresa.example/careers?country=DO",
        "talento": "https://empresa.example/talent", "linkedin_empresa": "https://www.linkedin.com/company/servicios",
        "roles_contacto": ["Talent Acquisition", "Head of Supply Chain"]})
    assert nueva and e["estado"] == "Descubierta" and e["tipo"] == "multinacional"
    assert len(e["fuentes_presencia"]) == 2 and e["fuentes_presencia"][1]["url"].startswith("https://zonafranca")
    assert e["roles"][1] == {"rol": "SAP Functional Analyst", "razon": "usuario de SAP"}
    assert e["razones"] == ["a", "b", "c"]  # las 3 razones principales
    assert e["estado_rastreo"] == "pendiente" and e["vacantes"] == "sin revisar"
    assert "ajuste" not in e and "interes" not in e  # sin puntuación numérica
    h = store.historial(e["id"])
    assert h[0]["a_estado"] == "Descubierta" and "https://empresa.example/rd" in h[0]["nota"]


def test_volver_a_guardar_actualiza_sin_perder_datos(store):
    a = empresa(store, "Telco Ejemplo", industria="telecomunicaciones", equipos=["Datos"])
    b, nueva = store.guardar_empresa({"nombre": "TELCO  ejemplo", "url_empleos": "https://t.do/empleos"})
    assert not nueva and a["id"] == b["id"] and b["equipos"] == ["Datos"] and b["industria"] == "telecomunicaciones"
    assert b["estado_rastreo"] == "pendiente"
    with pytest.raises(DatosError):
        store.update_empresa(a["id"], fuentes_presencia=[])


@pytest.mark.parametrize("campo,valor", [
    ("url_empleos", "https://www.linkedin.com/company/x/jobs"),
    ("url_empleos", "https://do.computrabajo.com/empresas/ofertas-de-trabajo-de-y"),
    ("linkedin_empresa", "https://www.linkedin.com/in/juan-perez"),
    ("linkedin_empresa", "https://empresa.example"),
    ("sitio_web", "empresa sin enlace"),
])
def test_rechaza_enlaces_invalidos_portales_y_perfiles_personales(store, campo, valor):
    with pytest.raises(DatosError):
        empresa(store, "Empresa X", **{campo: valor})


def test_portal_filtrado_puede_ser_de_un_portal_porque_no_se_rastrea(store):
    e = empresa(store, "Empresa Y", portal_rd="https://www.linkedin.com/company/y/jobs")
    assert e["portal_rd"].endswith("/jobs") and e["estado_rastreo"] == "sin página"


# -- seguimiento por empresa --------------------------------------------------------------
def test_flujo_de_estados_con_historial_y_fechas(store):
    e = empresa(store)
    for estado in ESTADOS[1:-1]:
        e = store.cambiar_estado(e["id"], estado, nota=f"nota {estado}")
        assert e["estado"] == estado
    h = store.historial(e["id"])
    assert [x["a_estado"] for x in h] == ESTADOS[:-1]
    assert [x["de_estado"] for x in h][1:] == ESTADOS[:-2]
    assert all(dt.datetime.fromisoformat(x["fecha"]) for x in h)
    assert h[2]["nota"] == "nota Investigando"


def test_mismo_estado_no_duplica_historial_y_estado_invalido(store):
    e = empresa(store)
    store.cambiar_estado(e["id"], "Descubierta")
    assert len(store.historial(e["id"])) == 1
    with pytest.raises(DatosError):
        store.cambiar_estado(e["id"], "Contratado")


def test_seguimiento_se_agenda_al_contactar_y_se_limpia_al_descartar(store):
    e = empresa(store)
    e = store.cambiar_estado(e["id"], "Contacté")
    assert e["seguimiento"] == (dt.date.today() + dt.timedelta(days=5)).isoformat()
    r = store.resumen()
    assert r["contactadas_semana"] == 1 and r["seguimientos"][0]["id"] == e["id"]
    e = store.cambiar_estado(e["id"], "Descartada")
    assert e["seguimiento"] == "" and store.resumen()["seguimientos"] == []
    with pytest.raises(DatosError):
        store.set_seguimiento(e["id"], "20-10-2026")


def test_resumen_cuenta_empresas_por_estado_y_vacantes(store):
    a = empresa(store, "A")
    empresa(store, "B")
    store.cambiar_estado(a["id"], "Me interesa")
    store.upsert_vacante("Analista", a["id"])
    r = store.resumen()
    assert set(r["por_estado"]) == set(ESTADOS)
    assert r["por_estado"]["Descubierta"] == 1 and r["por_estado"]["Me interesa"] == 1 and r["total_empresas"] == 2
    assert r["empresas_con_vacantes"] == 1 and r["vacantes_activas"] == 1
    assert store.get_empresa(a["id"])["vacantes"] == "hay vacantes"
    assert store.set_nota(a["id"], "Llamar el lunes")["nota"] == "Llamar el lunes"


# -- vacantes (comprobación secundaria) ---------------------------------------------------
def test_dedupe_de_vacantes_por_url_y_por_titulo(store):
    e = empresa(store)
    v1, n1 = store.upsert_vacante("Analista de Datos", e["id"], url="https://b.do/empleos/1?utm_source=x")
    v2, n2 = store.upsert_vacante("Analista de datos ", e["id"], url="https://b.do/empleos/1/#aplicar")
    assert n1 and not n2 and v1["id"] == v2["id"]
    _, n3 = store.upsert_vacante("ANALISTA DE DATOS", empresa_nombre="Banco Ejemplo")
    assert not n3 and len(store.vacantes()) == 1
    assert "estado" not in v1 and "ajuste" not in v1


def test_borrar_empresa_borra_sus_vacantes_e_historial(store):
    e = empresa(store)
    store.upsert_vacante("Analista", e["id"])
    store.remove_empresa(e["id"])
    assert store.vacantes() == [] and store.historial() == []


def test_base_de_datos_anterior_se_respalda_y_se_empieza_nueva(tmp_path):
    vieja = tmp_path / "oportunidades.db"
    con = sqlite3.connect(vieja)
    con.execute("CREATE TABLE empresas (id INTEGER PRIMARY KEY, nombre TEXT, interes INTEGER)")
    con.execute("INSERT INTO empresas (nombre, interes) VALUES ('Vieja', 80)")
    con.commit()
    con.close()
    with Store(vieja) as s:
        assert s.empresas() == [] and "fuentes_presencia" in columnas(s, "empresas")
    respaldos = list(tmp_path.glob("oportunidades.v1-*.db"))
    assert len(respaldos) == 1


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
        empresa(store, roles_contacto=[rol])


def test_contactos_son_roles_con_busqueda_de_linkedin(store):
    e = empresa(store, roles_contacto=["Head of Data", "Gerente de Innovación"])
    cts = contactos.contactos(e)
    assert [c["rol"] for c in cts] == ["Head of Data", "Gerente de Innovación"]
    assert set(cts[0]) == {"nombre", "rol", "fuente", "linkedin"} and cts[0]["nombre"] == ""
    assert cts[0]["linkedin"] == ("https://www.linkedin.com/search/results/people/?keywords="
                                  "Head+of+Data+Banco+Ejemplo")
    sin_roles = empresa(store, "Telco Ejemplo", industria="telecomunicaciones")
    assert len(contactos.contactos(sin_roles)) == 3  # sugeridos por industria
    assert contactos.url_linkedin_empresa(sin_roles).startswith("https://www.linkedin.com/search/results/companies/")


def test_personas_a_contactar_con_fuente_publica_y_sin_correos_ni_telefonos(store):
    e = empresa(store, roles_contacto=["Talent Acquisition"], personas=[
        {"nombre": "María Ejemplo", "cargo": "Gerente de Supply Chain", "fuente": "https://banco-ejemplo.com/equipo",
         "linkedin": "https://www.linkedin.com/in/maria-ejemplo/"},
        {"nombre": "Juan Ejemplo", "cargo": "Head of Data", "fuente": "https://noticias.example.com/nota"}])
    cts = contactos.contactos(e)
    assert [c["nombre"] for c in cts] == ["María Ejemplo", "Juan Ejemplo", ""]  # personas primero, luego cargos
    assert cts[0]["linkedin"] == "https://www.linkedin.com/in/maria-ejemplo/"
    assert cts[1]["linkedin"].startswith("https://www.linkedin.com/search/results/people/?keywords=Juan+Ejemplo")
    malas = [
        {"nombre": "Ana", "cargo": "CTO", "fuente": "https://x.com/a", "email": "ana@x.com"},  # correo
        {"nombre": "Ana 809-555-1234", "cargo": "CTO", "fuente": "https://x.com/a"},  # teléfono en el nombre
        {"nombre": "Ana", "cargo": "CTO"},  # sin fuente
        {"nombre": "Ana", "cargo": "CTO", "fuente": "https://www.linkedin.com/in/ana"},  # la fuente no puede ser LinkedIn
        {"nombre": "Ana", "cargo": "CTO", "fuente": "https://x.com/a", "linkedin": "https://x.com/ana"},  # no es perfil
    ]
    for mala in malas:
        with pytest.raises(DatosError):
            store.guardar_empresa({"nombre": "Otra Ejemplo", "fuentes_presencia": ["https://otra.example.com"],
                                   "personas": [mala]})


def test_base_anterior_sin_personas_se_actualiza(tmp_path):
    import sqlite3
    ruta = tmp_path / "vieja.db"
    s1 = Store(ruta)
    s1.conn.execute("ALTER TABLE empresas DROP COLUMN personas")
    s1.conn.commit(); s1.conn.close()
    s2 = Store(ruta)
    cols = {c["name"] for c in s2.conn.execute("PRAGMA table_info(empresas)")}
    assert "personas" in cols
