import json

import pytest

from conftest import fixture
from oportunidades import ajuste, ia, servicio


def test_vacante_buena_puntua_alto(perfil):
    v = {"titulo": "AI Integration Specialist", "ubicacion": "Santo Domingo",
         "descripcion": "Integrar LLM y RAG en procesos internos con Python, SQL y APIs. Modalidad híbrida, "
                        "lunes a viernes. 2 años de experiencia. " * 3}
    r = ajuste.heuristica(perfil, v)
    assert r["ajuste"] >= 75
    assert len(r["por_que_encaja"]) <= 3 and r["por_que_encaja"]
    assert r["alertas"] == []


def test_senales_de_alerta(perfil):
    r = ajuste.heuristica(perfil, {"titulo": "Gerente de Inteligencia Artificial", "ubicacion": "",
                                   "descripcion": fixture("vacante_pegada.txt")})
    alertas = " ".join(r["alertas"])
    assert "7+ años" in alertas                      # pide 5+ años en algo
    assert "presencial" in alertas                   # solo presencial
    assert "RD$85,000" in alertas and "100,000" in alertas  # salario por debajo del mínimo
    assert "fines de semana" in alertas              # lunes a sábado
    faltan = " ".join(r["faltantes"])
    assert "PyTorch" in faltan and "Kubernetes" in faltan
    assert "Python" not in faltan                    # ya lo tiene


def test_rol_vago(perfil):
    r = ajuste.heuristica(perfil, {"titulo": "Analista", "ubicacion": "Santo Domingo", "descripcion": "Urgente."})
    assert any("vaga" in a for a in r["alertas"]) and any("genérico" in a for a in r["alertas"])


def test_extrae_anos_y_salario():
    assert ajuste.anos_requeridos("Requisitos: 5+ years of experience with Python") == 5
    assert ajuste.anos_requeridos("Mínimo 3 años de experiencia") == 3
    assert ajuste.anos_requeridos("Experiencia deseable") == 0
    assert ajuste.salario_maximo("Salario: RD$ 60,000 - 75,000 mensuales") == 60000 or \
        ajuste.salario_maximo("Salario: RD$ 60,000 - 75,000 mensuales") == 75000
    assert ajuste.salario_maximo("Sueldo DOP 120.000") == 120000
    assert ajuste.salario_maximo("Sin salario indicado") == 0


def test_pegar_vacante_y_puntua(store, perfil):
    vac, nueva = servicio.pegar(store, perfil, fixture("vacante_pegada.txt"),
                                url="https://www.linkedin.com/jobs/view/123?trk=abc", empresa="Empresa de Servicios Ejemplo")
    assert nueva and vac["titulo"] == "Gerente de Inteligencia Artificial"
    assert vac["fuente"] == "pegado" and vac["estado"] == "Nuevo" and vac["ajuste"] is not None
    assert vac["puntuado_por"] == "heurística" and vac["alertas"]
    # pegarla otra vez no la duplica (misma URL sin parámetros de rastreo)
    _, otra = servicio.pegar(store, perfil, fixture("vacante_pegada.txt"), url="https://www.linkedin.com/jobs/view/123")
    assert not otra and len(store.vacantes()) == 1


def test_puntuar_con_ia_solo_envia_al_proveedor_elegido(store, perfil, monkeypatch):
    llamadas = {"claude": [], "openai": []}

    def falso(nombre):
        def f(sistema, usuario, modelo):
            llamadas[nombre].append((sistema, usuario, modelo))
            return json.dumps({"ajuste": 81, "por_que_encaja": ["a", "b", "c"], "alertas": ["x"], "faltantes": []})
        return f
    perfil["ia"] = {"proveedor": "claude", "modelo": ""}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    v, _ = store.upsert_vacante("AI Engineer", empresa_nombre="X", descripcion="LLM")
    r = ia.puntuar(perfil, v, {"claude": falso("claude"), "openai": falso("openai")})
    assert r["ajuste"] == 81 and r["puntuado_por"] == "claude"
    assert len(llamadas["claude"]) == 1 and llamadas["openai"] == []
    assert llamadas["claude"][0][2] == ia.MODELOS_POR_DEFECTO["claude"]
    enviado = llamadas["claude"][0][1]
    assert "AI Engineer" in enviado and "Python" in enviado and "profile.yaml" not in enviado


def test_sin_clave_usa_heuristica(store, perfil):
    perfil["ia"] = {"proveedor": "openai", "modelo": ""}
    assert not ia.disponible(perfil)
    v, _ = store.upsert_vacante("Analista de Datos", empresa_nombre="X", descripcion="SQL y Python")
    assert servicio.puntuar(store, perfil, v["id"])["puntuado_por"] == "heurística"
    with pytest.raises(ia.IAError):
        ia.completar(perfil, "s", "u")


def test_modo_agente_no_llama_api(perfil, monkeypatch):
    perfil["ia"] = {"proveedor": "agente", "modelo": ""}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert not ia.disponible(perfil)


def test_modelo_claude_por_defecto_y_configurable(store, perfil, monkeypatch):
    assert ia.MODELOS_POR_DEFECTO["claude"] == "claude-sonnet-5-5"
    usados = []
    def falso(sistema, usuario, modelo):
        usados.append(modelo)
        return json.dumps({"ajuste": 50, "por_que_encaja": ["a", "b", "c"], "alertas": [], "faltantes": []})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    v, _ = store.upsert_vacante("AI Engineer", empresa_nombre="X", descripcion="LLM")
    perfil["ia"] = {"proveedor": "claude", "modelo": "claude-opus-5-5"}
    ia.puntuar(perfil, v, {"claude": falso})
    assert usados == ["claude-opus-5-5"]
