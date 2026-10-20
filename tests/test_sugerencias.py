import json
import shutil
import subprocess
import sys

import pytest
import yaml

import app as tablero
from oportunidades import config, perfil as pf, redaccion, sugerencias as sg
from oportunidades.db import INDUSTRIAS

ROOT = config.ROOT
AREAS_PEDIDAS = ["tecnología", "datos y análisis", "finanzas y contabilidad", "logística y cadena de suministro",
                 "operaciones y procesos", "ventas", "marketing", "diseño", "recursos humanos", "salud", "educación",
                 "servicio al cliente", "legal", "manufactura", "turismo y hotelería"]


def roles(s):
    return [r["rol"] for r in s["roles"]]


# -- el mapa ------------------------------------------------------------------------------
def test_el_mapa_cubre_todas_las_areas_con_contenido():
    mapa = sg.cargar_mapa()
    assert sg.areas() == AREAS_PEDIDAS
    todas = {sg.normalizar(h) for a in mapa["areas"] for h in a["habilidades"]}
    for a in mapa["areas"]:
        assert a["descripcion"] and len(a["palabras"]) >= 5 and len(a["habilidades"]) >= 6 and len(a["roles"]) >= 4, a["area"]
        for r in a["roles"]:
            assert r["rol"] and r["razon"].endswith(".") and r["habilidades"], r
            # las habilidades que suben un rol también se pueden sugerir
            assert {sg.normalizar(h) for h in r["habilidades"]} <= todas, r["rol"]


def test_las_industrias_antiguas_tienen_equivalencia():
    equivalencias = sg.cargar_mapa()["industrias_antiguas"]
    assert set(equivalencias) == set(INDUSTRIAS)
    assert all(a in AREAS_PEDIDAS for areas in equivalencias.values() for a in areas)


@pytest.mark.parametrize("area", AREAS_PEDIDAS)
def test_cada_area_sugiere_sus_roles_y_habilidades(area):
    s = sg.sugerir({"intereses": [area]})
    propia = next(a for a in sg.cargar_mapa()["areas"] if a["area"] == area)
    assert s["areas"] == [area]
    assert roles(s) == [r["rol"] for r in propia["roles"]][:sg.MAX_ROLES]
    assert [h["nombre"] for h in s["habilidades"]] == propia["habilidades"][:sg.MAX_HABILIDADES]
    assert all(r["razon"] for r in s["roles"])


# -- cómo se detecta y se ordena ------------------------------------------------------------
@pytest.mark.parametrize("campo, texto, area", [
    ("puesto_actual", "Contador en una firma de auditoría", "finanzas y contabilidad"),
    ("puesto_actual", "Cajera en un supermercado", "servicio al cliente"),
    ("puesto_actual", "Recepcionista de un hotel en Punta Cana", "turismo y hotelería"),
    ("puesto_actual", "Operario de producción en zona franca", "manufactura"),
    ("estudios", "Licenciatura en Enfermería", "salud"),
    ("estudios", "Licenciatura en Educación Básica", "educación"),
    ("estudios", "Derecho", "legal"),
    ("estudios", "Diseño Gráfico", "diseño"),
    ("estudios", "Mercadeo", "marketing"),
    ("estudios", "Psicología industrial", "recursos humanos"),
    ("estudios", "Ingeniería en Sistemas", "tecnología"),
])
def test_detecta_el_area_por_lo_que_estudiaste_o_tu_trabajo(campo, texto, area):
    s = sg.sugerir({campo: texto})
    assert area in s["areas"]
    assert s["areas"][0] == area or len(s["areas"]) > 1


def test_no_confunde_palabras_parecidas():
    assert "educación" not in sg.sugerir({"estudios": "Maestría en finanzas"})["areas"]
    assert "salud" not in sg.sugerir({"puesto_actual": "Técnico de medición"})["areas"]
    assert "tecnología" not in sg.sugerir({"puesto_actual": "Community manager de redes sociales"})["areas"]


def test_el_porque_usa_tu_experiencia_y_tus_habilidades():
    s = sg.sugerir({"puesto_actual": "Contador en una firma de auditoría."})
    assert s["roles"][0] == {"rol": "Contador", "razon": "Encaja con tu experiencia como Contador en una firma de auditoría.",
                             "origen": "mapa"}
    s = sg.sugerir({"estudios": "Enfermería"})
    assert s["roles"][0]["razon"] == "Encaja con lo que estudiaste (Enfermería)."
    # Figma ya la tienes: Diseñador UX/UI sube por encima de Diseñador gráfico.
    s = sg.sugerir({"intereses": ["diseño"], "habilidades": ["figma"]})
    assert s["roles"][0] == {"rol": "Diseñador UX/UI", "razon": "Usa Figma, que ya tienes.", "origen": "mapa"}


def test_interes_elegido_pesa_mas_que_una_mencion_suelta():
    s = sg.sugerir({"intereses": ["legal"], "experiencia": "Ayudo con las ventas de la tienda de mi familia."})
    assert s["areas"] == ["legal", "ventas"] and roles(s)[0] == "Abogado corporativo"


def test_reparte_por_turnos_entre_areas_fuertes():
    """Muchas habilidades de un área no tapan el área donde trabajas ni las que elegiste."""
    ana = pf.importar(ROOT / "profile.example.yaml")
    enfermera = ana | {"intereses": ana["intereses"] + ["salud"], "puesto_actual": "Enfermera en una clínica"}
    s = sg.sugerir(enfermera)
    assert s["areas"][0] == "salud" and roles(s)[0] == "Enfermera o enfermero"
    mapa = {a["area"]: {r["rol"] for r in a["roles"]} for a in sg.cargar_mapa()["areas"]}
    fuertes = ["salud", "tecnología", "datos y análisis", "operaciones y procesos"]
    primera_vuelta = roles(s)[:len(fuertes)]
    assert [next(a for a in fuertes if r in mapa[a]) for r in primera_vuelta] == fuertes
    # Ana: cada área que eligió tiene un rol entre los primeros, y la débil («ventas», solo mencionada) no.
    s = sg.sugerir(ana)
    primeros = roles(s)[:4]
    for area in ana["intereses"]:
        assert any(r in mapa[area] for r in primeros), area
    assert not any(r in mapa["ventas"] for r in roles(s))


def test_coincidencia_de_habilidades():
    assert sg._coincide("Excel", "Excel avanzado") and sg._coincide("IA generativa (LLM)", "LLM")
    assert sg._coincide("Diseño UX", "diseno ux") and not sg._coincide("Java", "JavaScript")


def test_sin_datos_no_sugiere_nada_y_hay_limites():
    assert sg.sugerir({}) == {"areas": [], "habilidades": [], "roles": []}
    s = sg.sugerir({"intereses": AREAS_PEDIDAS})
    assert len(s["roles"]) == sg.MAX_ROLES and len(s["habilidades"]) == sg.MAX_HABILIDADES
    assert len({sg.normalizar(r["rol"]) for r in s["roles"]}) == len(s["roles"])


def test_las_sugerencias_del_agente_van_primero_sin_repetir():
    agente = {"habilidades": ["Conciliaciones bancarias", "SAP FI"],
              "roles": [{"rol": "Analista contable de cuentas por pagar", "razon": "Tu práctica en cuentas por pagar."},
                        {"rol": "contador", "razon": "Lo pediste."}]}
    s = sg.sugerir({"intereses": ["finanzas y contabilidad"], "sugerencias": agente})
    assert [h["nombre"] for h in s["habilidades"][:2]] == ["Conciliaciones bancarias", "SAP FI"]
    assert [h["origen"] for h in s["habilidades"][:2]] == ["agente", "agente"]
    assert sum(sg.normalizar(h["nombre"]) == "conciliaciones bancarias" for h in s["habilidades"]) == 1
    assert roles(s)[:2] == ["Analista contable de cuentas por pagar", "contador"] and "Contador" not in roles(s)
    assert sum(r["origen"] == "mapa" for r in s["roles"]) <= sg.MAX_ROLES


# -- el tablero usa la misma lógica en JavaScript ---------------------------------------------
CASOS = [
    {},
    {"intereses": ["tecnología", "Datos y Análisis"], "habilidades": ["Excel avanzado", "LLM"]},
    {"puesto_actual": "Cajera en un supermercado", "estudios": "Contabilidad", "anos_experiencia": 2},
    {"intereses": ["diseño"], "intereses_otra": "fotografía de bodas", "habilidades": ["Figma", "Canva"]},
    {"intereses": AREAS_PEDIDAS, "habilidades": ["Excel", "Negociación", "Atención al cliente"]},
    {"estudios": "Maestría en finanzas.", "experiencia": "Trabajé en un hotel y en una clínica.",
     "sugerencias": {"habilidades": ["SAP FI"], "roles": [{"rol": "Analista de tesorería", "razon": "Por tu maestría."}]}},
]


@pytest.mark.skipif(not shutil.which("node"), reason="node no está instalado")
def test_javascript_y_python_sugieren_exactamente_lo_mismo():
    script = ("const s = require(process.argv[1]); const mapa = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));"
              "const casos = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              "process.stdout.write(JSON.stringify(casos.map((c) => s.sugerir(c, mapa))));")
    r = subprocess.run(["node", "-e", script, str(ROOT / "static" / "sugerencias.js"), str(sg.MAPA)],
                       input=json.dumps(CASOS), capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(r.stdout) == [sg.sugerir(c) for c in CASOS]


# -- perfil: campos nuevos, migración y CLI ---------------------------------------------------
def _escribir_perfil(datos):
    path = config.profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")


def test_migra_un_perfil_anterior_con_industrias():
    _escribir_perfil({"nombre": "Viejo", "industrias": ["banca", "logística", "retail/distribución", "otra"],
                      "roles_objetivo": ["Analista"]})
    p = pf.cargar()
    assert p["intereses"] == ["finanzas y contabilidad", "logística y cadena de suministro", "ventas"]
    assert p["industrias"] == ["banca", "logística", "retail/distribución", "otra"]  # no se pierde nada
    assert p["roles_objetivo"] == ["Analista"] and p["estudios"] == "" and p["sugerencias"]["roles"] == []
    p["intereses"] = []
    pf.guardar(p)
    assert pf.cargar()["intereses"] == []  # ya migrado: si los vacías, no vuelven


def test_intereses_validos_con_o_sin_tildes():
    p = pf.set_campo(pf.cargar(), "intereses", "Tecnologia; DISEÑO; tecnología")
    assert p["intereses"] == ["tecnología", "diseño"]
    with pytest.raises(pf.PerfilError, match="intereses_otra"):
        pf.set_campo(pf.cargar(), "intereses", "astronautas")


def test_faltantes_con_el_flujo_nuevo():
    falta = pf.faltantes(pf.cargar())
    assert {"intereses", "habilidades", "roles_objetivo", "idiomas", "estudios / puesto_actual"} <= set(falta)
    p = pf.cargar() | {"intereses_otra": "agricultura", "puesto_actual": "Agrónomo"}
    assert "intereses" not in pf.faltantes(p) and "estudios / puesto_actual" not in pf.faltantes(p)


def test_el_ejemplo_pasa_por_el_flujo_nuevo():
    ana = pf.importar(ROOT / "profile.example.yaml")
    assert ana["intereses"] and ana["estudios"] and ana["puesto_actual"] and pf.faltantes(ana) == []
    s = sg.sugerir(ana)
    sugeridos = roles(s)
    assert all(r in sugeridos for r in ana["roles_objetivo"])  # Ana eligió sus roles entre las sugerencias
    assert "industrias" not in yaml.safe_load((ROOT / "profile.example.yaml").read_text(encoding="utf-8"))


def test_cli_sugerir_y_guardar_sugerencias_del_agente(tmp_path):
    pf.guardar(pf.set_campo(pf.cargar(), "puesto_actual", "Contador"))
    corre = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts" / "perfil.py"), *a], capture_output=True,
                                      text=True, encoding="utf-8")
    r = corre("sugerir")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["roles"][0]["rol"] == "Contador"
    archivo = tmp_path / "s.json"
    archivo.write_text(json.dumps({"habilidades": ["NIIF"], "roles": [{"rol": "Analista de costos", "razon": "Por tu trabajo."}]}),
                       encoding="utf-8")
    r = corre("sugerencias", "--archivo", str(archivo))
    assert r.returncode == 0 and "1 habilidades y 1 roles" in r.stdout, r.stderr
    assert sg.sugerir(pf.cargar())["roles"][0] == {"rol": "Analista de costos", "razon": "Por tu trabajo.", "origen": "agente"}
    archivo.write_text(json.dumps({"roles": [{"razon": "sin rol"}]}), encoding="utf-8")
    assert corre("sugerencias", "--archivo", str(archivo)).returncode == 1
    assert corre("sugerencias", "--borrar").returncode == 0 and pf.cargar()["sugerencias"]["roles"] == []


# -- tablero y cartas -------------------------------------------------------------------------
def test_la_pagina_trae_el_mapa_y_las_tarjetas_de_areas():
    c = tablero.crear_app().test_client()
    html = c.get("/").get_data(as_text=True)
    assert html.count('name="intereses"') == len(AREAS_PEDIDAS) and 'id="interes-otra"' in html
    assert "window.SUGERENCIAS" in html and "/static/sugerencias.js" in html
    assert 'name="industrias"' not in html
    body = {"intereses": ["salud"], "intereses_otra": "deportes", "estudios": "Enfermería", "puesto_actual": "Enfermera",
            "anos_experiencia": "4", "industrias": ["banca"]}
    p = c.post("/api/perfil", json=body).get_json()["perfil"]
    assert (p["intereses"], p["intereses_otra"], p["estudios"], p["puesto_actual"], p["anos_experiencia"]) == \
        (["salud"], "deportes", "Enfermería", "Enfermera", 4)
    assert p["industrias"] == []  # el asistente ya no cambia las industrias
    assert c.post("/api/perfil", json={"intereses": ["astronautas"]}).status_code == 400


def test_la_carta_sin_resumen_usa_puesto_y_estudios():
    p = {"puesto_actual": "Cajera en un supermercado", "anos_experiencia": 2, "estudios": "Contabilidad"}
    assert redaccion.experiencia(p, "es") == ("Mi experiencia más reciente es como Cajera en un supermercado, "
                                              "con 2 años de experiencia. Estudié Contabilidad.")
    assert redaccion.experiencia({"estudios": "Contabilidad"}, "en") == "I studied Contabilidad."
    assert redaccion.experiencia({"experiencia": "Mi resumen."}, "es") == "Mi resumen."
