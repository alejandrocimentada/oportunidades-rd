import pytest

from oportunidades import redaccion
from oportunidades.db import DatosError


def _vacante(store, idioma_texto="es"):
    desc = ("Buscamos integrar IA en los procesos de la empresa, con Python y SQL." if idioma_texto == "es"
            else "We are looking for an engineer to integrate AI into our processes with Python and SQL.")
    v, _ = store.upsert_vacante("AI Integration Specialist", empresa_nombre="Banco Ejemplo", descripcion=desc)
    store.guardar_puntuacion(v["id"], 80, ["Coincide con tu objetivo.", "Pide Python."], [], [], "heurística")
    return v


def test_no_genera_para_vacantes_nuevas(store, perfil):
    v = _vacante(store)
    with pytest.raises(DatosError, match="Me interesa"):
        redaccion.generar(store, perfil, v["id"])
    store.cambiar_estado(v["id"], "Descartado")
    with pytest.raises(DatosError):
        redaccion.generar(store, perfil, v["id"])


def test_genera_mensaje_y_carta_en_espanol(store, perfil):
    v = _vacante(store)
    store.cambiar_estado(v["id"], "Me interesa")
    paths = redaccion.generar(store, perfil, v["id"])
    assert set(paths) == {"mensaje", "carta"}
    for p in paths.values():
        assert p.exists() and "documentos" in str(p)
    mensaje = redaccion.leer(paths["mensaje"])
    carta = redaccion.leer(paths["carta"])
    assert "AI Integration Specialist" in mensaje and "Banco Ejemplo" in mensaje and mensaje.startswith("Hola")
    assert "Estimado equipo" in carta and "Ana Ejemplo Pérez" in carta
    v = store.get_vacante(v["id"])
    assert v["mensaje_path"] == str(paths["mensaje"]) and v["carta_path"] == str(paths["carta"])


def test_idioma_segun_la_vacante(store, perfil):
    v = _vacante(store, "en")
    assert v["idioma"] == "en"
    store.cambiar_estado(v["id"], "Me interesa")
    carta = redaccion.leer(redaccion.generar(store, perfil, v["id"], ("carta",))["carta"])
    assert "Dear Hiring Team" in carta
    forzada = redaccion.leer(redaccion.generar(store, perfil, v["id"], ("carta",), idioma="es")["carta"])
    assert "Estimado equipo" in forzada


def test_con_ia_usa_el_proveedor(store, perfil, monkeypatch):
    v = _vacante(store)
    store.cambiar_estado(v["id"], "Aplicado")
    perfil["ia"] = {"proveedor": "openai", "modelo": "modelo-x"}
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    vistos = []

    def falso(sistema, usuario, modelo):
        vistos.append(modelo)
        return "Texto redactado por la IA."
    paths = redaccion.generar(store, perfil, v["id"], llamadas={"openai": falso})
    assert vistos == ["modelo-x", "modelo-x"]
    assert redaccion.leer(paths["carta"]) == "Texto redactado por la IA."


def test_guardar_texto_del_agente(store, perfil):
    v = _vacante(store)
    store.cambiar_estado(v["id"], "Me interesa")
    p = redaccion.guardar_texto(store, store.get_vacante(v["id"]), "mensaje", "Hola, texto del agente.")
    assert redaccion.leer(p) == "Hola, texto del agente."
    assert "NO se envía solo" in p.read_text(encoding="utf-8")
