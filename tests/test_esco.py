import json
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

import app as tablero
from oportunidades import config, sugerencias as sg

ROOT = config.ROOT
MUESTRA = ROOT / "tests" / "fixtures" / "esco"  # CSV con el formato oficial de ESCO y datos de muestra
FRASE = "This service uses the ESCO classification of the European Commission."  # condición de ESCO, exacta
sys.path.insert(0, str(ROOT / "scripts"))
import construir_esco  # noqa: E402


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    destino = tmp_path_factory.mktemp("esco") / "esco.json"
    construir_esco.construir([MUESTRA], destino, version="v1.2.1", competencias=MUESTRA / "competencias_esco.json",
                             curadas=MUESTRA / "curadas.json")
    return json.loads(destino.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def esco(indice):
    return sg.preparar_esco(indice)


def es(resultados):
    return [r["es"] for r in resultados]


# -- construir el índice ------------------------------------------------------------------------
def test_construye_una_lista_de_nombres_cortos(indice):
    assert indice["licencia"] == "CC BY 4.0" and indice["adaptado"] is True and indice["fuente"] == "ESCO v1.2.1"
    assert indice["atribucion"].startswith(FRASE) and "Versión adaptada" in indice["atribucion"] and "curada" in indice["atribucion"]
    etiquetas = [h[0] for h in indice["h"]]
    assert etiquetas == ["Excel", "Power BI", "Python", "Scrum", "Trabajo en equipo", "Hojas de cálculo",
                         "Técnicas de presentación visual", "Asistencia sanitaria", "Atención al paciente", "Contabilidad",
                         "Diseño gráfico", "Estadística", "Inglés", "Movilidad como servicio", "SQL"]
    origen = {h[0]: h[4] for h in indice["h"]}
    assert origen["Excel"] == origen["Scrum"] == "curada" and origen["Python"] == "esco"
    assert origen["Hojas de cálculo"] == origen["Trabajo en equipo"] == "reescrita"
    # Fuera: tareas sin reescribir, más de 4 palabras, sin ocupaciones, obsoletas o marcadas «quitar».
    assert indice["h"][2][1] == "Python"  # sin «(computer programming)»
    contable = next(o for o in indice["o"] if o[0] == "contable")
    assert [indice["h"][i][0] for i in contable[3]] == ["Hojas de cálculo", "Contabilidad"]


# -- buscador -----------------------------------------------------------------------------------
@pytest.mark.parametrize("consulta", ["estadistica", "ESTADÍSTICA", "estadística", "Estadistica  ", "statistics"])
def test_busca_sin_importar_tildes_mayusculas_ni_idioma(esco, consulta):
    assert es(sg.buscar_habilidades(consulta, esco)) == ["Estadística"]


def test_orden_exacta_empieza_por_palabra_y_popularidad(esco):
    assert es(sg.buscar_habilidades("excel", esco)) == ["Excel"]
    assert es(sg.buscar_habilidades("python", esco)) == ["Python"]
    # empieza por: la más usada primero; los sinónimos después de los nombres
    r = sg.buscar_habilidades("te", esco)
    assert es(r) == ["Trabajo en equipo", "Técnicas de presentación visual", "Contabilidad"] and r[2]["sinonimo"] == "teneduría de libros"
    assert es(sg.buscar_habilidades("pre", esco)) == ["Técnicas de presentación visual"]  # una palabra empieza por «pre»


def test_as_no_encuentra_palabras_vacias(esco):
    assert es(sg.buscar_habilidades("as", esco)) == ["Asistencia sanitaria"]  # no «mobility as a service»
    assert sg.buscar_habilidades("ual", esco) == []  # nunca a mitad de palabra


def test_minimo_dos_letras_y_maximo_ocho(esco, indice):
    assert sg.buscar_habilidades("e", esco) == [] and sg.buscar_habilidades("", esco) == []
    grande = sg.preparar_esco(indice | {"h": [[f"gestión {i}", f"management {i}", [], 1, "esco"] for i in range(30)]})
    assert len(sg.buscar_habilidades("ge", grande)) == sg.MAX_RESULTADOS == 8


# -- ocupaciones de ESCO en las sugerencias ------------------------------------------------------
def test_tu_puesto_sugiere_la_ocupacion_y_sus_habilidades(esco):
    s = sg.sugerir({"puesto_actual": "Contador en una firma pequeña", "habilidades": ["contabilidad"]}, esco=esco)
    esco_roles = [r for r in s["roles"] if r["origen"] == "esco"]
    assert esco_roles == [{"rol": "Contable", "razon": "Ocupación de ESCO parecida a tu trabajo actual.", "origen": "esco"}]
    habs = [h["nombre"] for h in s["habilidades"] if h["origen"] == "esco"]
    assert habs == ["Hojas de cálculo"]  # no repite lo que ya tienes  # no repite lo que ya tienes


def test_tus_habilidades_sugieren_ocupaciones_que_las_piden(esco):
    s = sg.sugerir({"habilidades": ["Hojas de cálculo", "sql"]}, esco=esco)
    assert s["roles"] == [{"rol": "Analista de datos", "origen": "esco",
                           "razon": "Según ESCO, pide Hojas de cálculo y SQL, que ya tienes."}]
    # las otras esenciales de esa ocupación, de la más usada a la menos usada
    assert [h["nombre"] for h in s["habilidades"]] == ["Python", "Trabajo en equipo", "Estadística"]
    assert sg.sugerir({"habilidades": ["Excel", "sql"]}, esco=esco)["roles"] == []  # las curadas no tienen ocupaciones


def test_tus_roles_traen_sus_habilidades_esenciales(esco):
    s = sg.sugerir({"roles_objetivo": ["Diseñador gráfico"]}, esco=esco)
    assert [h["nombre"] for h in s["habilidades"]] == ["Técnicas de presentación visual", "Diseño gráfico"]
    assert s["roles"] == []  # ya lo elegiste: no se repite como sugerencia


def test_esco_comparte_turnos_y_no_duplica_roles_del_mapa(esco):
    s = sg.sugerir({"intereses": ["datos y análisis"], "habilidades": ["Hojas de cálculo", "SQL"]}, esco=esco)
    nombres = [sg.normalizar(r["rol"]) for r in s["roles"]]
    assert nombres.count("analista de datos") == 1 and s["roles"][0]["origen"] == "mapa"


# -- el navegador usa la misma lógica ---------------------------------------------------------
CONSULTAS = ["as", "te", "pre", "ual", "python", "teneduria", "contador", "computadora", "excel", "Estadistica", "ESTADÍSTICA", "statistics", "diseno grafico", "datos visual", "sql", "e", "",
             "bookkeep", "cuidado del", "zzz"]
PERFILES = [{"puesto_actual": "Contador en una firma pequeña", "habilidades": ["contabilidad"]},
            {"habilidades": ["Excel", "sql", "Python"], "intereses": ["datos y análisis"]},
            {"roles_objetivo": ["Diseñador gráfico", "enfermera"], "puesto_actual": "Enfermera"},
            {"intereses": ["salud"], "estudios": "Enfermería", "habilidades": ["patient care", "Inglés"]},
            {"puesto_actual": "Contadora y mesera", "roles_objetivo": ["contador"], "habilidades": ["computadora"]}]


@pytest.mark.skipif(not shutil.which("node"), reason="node no está instalado")
def test_javascript_y_python_buscan_y_sugieren_lo_mismo(indice, esco, tmp_path):
    (tmp_path / "esco.json").write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
    script = ("const s = require(process.argv[1]); const fs = require('fs');"
              "const mapa = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));"
              "const esco = s.prepararEsco(JSON.parse(fs.readFileSync(process.argv[3], 'utf8')));"
              "const e = JSON.parse(fs.readFileSync(0, 'utf8'));"
              "process.stdout.write(JSON.stringify({b: e.consultas.map((q) => s.buscarHabilidades(q, esco)),"
              " s: e.perfiles.map((p) => s.sugerir(p, mapa, esco))}));")
    r = subprocess.run(["node", "-e", script, str(ROOT / "static" / "sugerencias.js"), str(sg.MAPA), str(tmp_path / "esco.json")],
                       input=json.dumps({"consultas": CONSULTAS, "perfiles": PERFILES}), capture_output=True, text=True,
                       encoding="utf-8", check=True)
    js = json.loads(r.stdout)
    assert js["b"] == [sg.buscar_habilidades(q, esco) for q in CONSULTAS]
    assert js["s"] == [sg.sugerir(p, esco=esco) for p in PERFILES]


# -- el índice real que se publica ---------------------------------------------------------------
def test_el_indice_publicado_es_de_esco_y_cabe():
    assert sg.ESCO.exists(), "Falta static/esco.json: python scripts/construir_esco.py --origen <descarga de ESCO>"
    datos = json.loads(sg.ESCO.read_text(encoding="utf-8"))
    assert datos["fuente"] == "ESCO v1.2.1" and datos["licencia"] == "CC BY 4.0" and datos["adaptado"] is True
    assert datos["atribucion"].startswith(FRASE)
    assert 2400 <= len(datos["h"]) <= 2800 and len(datos["o"]) > 2500
    assert {h[4] for h in datos["h"]} == {"esco", "reescrita", "curada"}
    assert sg.ESCO.stat().st_size < 1_500_000  # ~1 MB; ~0.2 MB con gzip
    esco = sg.cargar_esco()
    assert es(sg.buscar_habilidades("excel", esco))[0] == "Excel"
    assert es(sg.buscar_habilidades("python", esco))[0] == "Python"
    assert "Movilidad como servicio" not in es(sg.buscar_habilidades("as", esco))  # «mobility as a service»
    assert all(x.startswith("Gestión") for x in es(sg.buscar_habilidades("ges", esco)))
    for consulta in ("contabilidad", "contabilidád", "accounting", "diseño gráfico", "diseno grafico", "python"):
        assert sg.buscar_habilidades(consulta, esco), consulta


def test_entiende_palabras_de_rd_aunque_esco_use_las_de_espana():
    esco = sg.cargar_esco()
    assert any("ordenador" in r["es"] for r in sg.buscar_habilidades("computadora", esco))
    assert sg.buscar_habilidades("mercadeo", esco)[0]["es"] == "Marketing"
    assert any("contab" in r["es"].lower() for r in sg.buscar_habilidades("contador", esco))
    s = sg.sugerir({"puesto_actual": "Contadora en una ferretería"}, esco=esco)
    assert {"rol": "Contable", "razon": "Ocupación de ESCO parecida a tu trabajo actual.", "origen": "esco"} in s["roles"]
    s = sg.sugerir({"puesto_actual": "Mesero en un restaurante"}, esco=esco)
    assert any("camarero" in sg.normalizar(r["rol"]) for r in s["roles"] if r["origen"] == "esco")


def test_no_repite_un_rol_en_masculino_y_femenino():
    s = sg.sugerir({"puesto_actual": "Enfermera", "intereses": ["salud"]})
    enfermeria = [r["rol"] for r in s["roles"] if "enfermer" in sg.normalizar(r["rol"])]
    assert enfermeria == ["Enfermera o enfermero"]


def test_la_atribucion_de_esco_esta_en_la_pagina_y_el_readme():
    html = tablero.crear_app().test_client().get("/").get_data(as_text=True)
    texto = " ".join(re.sub(r"<[^>]+>", "", html).split())
    assert FRASE in texto and "versión adaptada" in texto and "curadas" in texto and "CC BY 4.0" in texto and "esco.ec.europa.eu" in html
    for readme, adaptada in (("README.md", "Versión adaptada"), ("README.en.md", "Adapted version")):
        t = (ROOT / readme).read_text(encoding="utf-8")
        assert FRASE in t and adaptada in t and "CC BY 4.0" in t and "esco.ec.europa.eu" in t


def test_cli_busca_habilidades():
    if not sg.ESCO.exists():
        pytest.skip("sin índice")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "perfil.py"), "buscar-habilidad", "contabilidad"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and json.loads(r.stdout), r.stderr
