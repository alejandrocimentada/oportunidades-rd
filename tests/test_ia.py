import pytest

from oportunidades import ia


def test_sin_clave_no_hay_ia_y_modo_agente_no_llama_api(perfil, monkeypatch):
    perfil["ia"] = {"proveedor": "openai", "modelo": ""}
    assert not ia.disponible(perfil)
    with pytest.raises(ia.IAError):
        ia.completar(perfil, "s", "u")
    perfil["ia"] = {"proveedor": "agente", "modelo": ""}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert not ia.disponible(perfil)


def test_solo_envia_al_proveedor_elegido_con_el_modelo_por_defecto_o_el_configurado(perfil, monkeypatch):
    assert ia.MODELOS_POR_DEFECTO["claude"] == "claude-sonnet-5-5"
    llamadas = {"claude": [], "openai": []}

    def falso(nombre):
        def f(sistema, usuario, modelo):
            llamadas[nombre].append(modelo)
            return "ok"
        return f
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    funcs = {"claude": falso("claude"), "openai": falso("openai")}
    perfil["ia"] = {"proveedor": "claude", "modelo": ""}
    assert ia.completar(perfil, "s", "u", funcs) == "ok"
    perfil["ia"] = {"proveedor": "claude", "modelo": "claude-opus-5-5"}
    ia.completar(perfil, "s", "u", funcs)
    assert llamadas == {"claude": ["claude-sonnet-5-5", "claude-opus-5-5"], "openai": []}
    assert "profile.yaml" not in str(ia.perfil_para_ia(perfil))
