import pytest

from conftest import empresa
from oportunidades import redaccion
from oportunidades.db import DatosError


def _empresa(store):
    return empresa(store, "Distribuidora Ejemplo", presencia_rd="Centro de distribución en Santo Domingo",
                   equipos=["Supply chain / planificación", "BI y analítica"],
                   roles=[{"rol": "Supply Chain Analyst", "razon": "Planificación de demanda con SAP."},
                          {"rol": "BI Analyst", "razon": "Tableros en Power BI."}],
                   razones=["Consumo masivo con planificación manual.", "Usa SAP."])


def test_no_genera_para_empresas_descubiertas_o_descartadas(store, perfil):
    e = _empresa(store)
    with pytest.raises(DatosError, match="Me interesa"):
        redaccion.generar(store, perfil, e["id"])
    store.cambiar_estado(e["id"], "Descartada")
    with pytest.raises(DatosError):
        redaccion.generar(store, perfil, e["id"])


def test_mensaje_y_carta_se_adaptan_al_equipo_y_rol_y_enlazan_al_trabajo(store, perfil):
    e = _empresa(store)
    store.cambiar_estado(e["id"], "Me interesa")
    paths = redaccion.generar(store, perfil, e["id"])
    assert set(paths) == {"mensaje", "carta"}
    for p in paths.values():
        assert p.exists() and "documentos" in str(p)
    mensaje, carta = redaccion.leer(paths["mensaje"]), redaccion.leer(paths["carta"])
    assert mensaje.startswith("Hola") and "Supply chain / planificación" in mensaje and "Supply Chain Analyst" in mensaje
    assert perfil["enlaces"]["portafolio"] in mensaje
    assert "Estimado equipo" in carta and "Ana Ejemplo Pérez" in carta and "Distribuidora Ejemplo" in carta
    assert perfil["enlaces"]["portafolio"] in carta and perfil["enlaces"]["github"] in carta
    e = store.get_empresa(e["id"])
    assert e["mensaje_path"] == str(paths["mensaje"]) and e["carta_path"] == str(paths["carta"])


def test_elegir_rol_e_idioma(store, perfil):
    e = _empresa(store)
    store.cambiar_estado(e["id"], "Investigando")
    msg = redaccion.leer(redaccion.generar(store, perfil, e["id"], ("mensaje",), rol="BI Analyst")["mensaje"])
    assert "BI Analyst" in msg and "Supply Chain Analyst" not in msg
    carta = redaccion.leer(redaccion.generar(store, perfil, e["id"], ("carta",), idioma="en")["carta"])
    assert "Dear Hiring Team" in carta


def test_con_ia_usa_el_proveedor_y_le_pasa_equipo_rol_y_enlaces(store, perfil, monkeypatch):
    e = _empresa(store)
    store.cambiar_estado(e["id"], "Contacté")
    perfil["ia"] = {"proveedor": "openai", "modelo": "modelo-x"}
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    vistos = []

    def falso(sistema, usuario, modelo):
        vistos.append((modelo, usuario))
        return "Texto redactado por la IA."
    paths = redaccion.generar(store, perfil, e["id"], llamadas={"openai": falso})
    assert [m for m, _ in vistos] == ["modelo-x", "modelo-x"]
    assert "Supply Chain Analyst" in vistos[0][1] and perfil["enlaces"]["portafolio"] in vistos[0][1]
    assert redaccion.leer(paths["carta"]) == "Texto redactado por la IA."


def test_guardar_texto_del_agente(store, perfil):
    e = _empresa(store)
    store.cambiar_estado(e["id"], "Me interesa")
    p = redaccion.guardar_texto(store, store.get_empresa(e["id"]), "mensaje", "Hola, texto del agente.")
    assert redaccion.leer(p) == "Hola, texto del agente."
    assert "NO se envía solo" in p.read_text(encoding="utf-8")
