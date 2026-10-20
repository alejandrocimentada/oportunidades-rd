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
    construir_esco.construir([MUESTRA], destino, version="v1.2.1")
    return json.loads(destino.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def esco(indice):
    return sg.preparar_esco(indice)


def es(resultados):
    return [r["es"] for r in resultados]


# -- construir el índice ------------------------------------------------------------------------
def test_construye_un_indice_compacto(indice):
    assert indice["licencia"] == "CC BY 4.0" and indice["adaptado"] is True and indice["fuente"] == "ESCO v1.2.1"
    assert indice["atribucion"].startswith(FRASE) and "Versión adaptada" in indice["atribucion"]
    etiquetas = [h[0] for h in indice["h"]]
    assert "habilidad obsoleta" not in etiquetas  # solo conceptos publicados («released»)
    assert len(etiquetas) == 10 and etiquetas[0] == "usar software de hojas de cálculo"  # la más usada, primero
    excel = indice["h"][0]
    assert excel[1] == "use spreadsheets software" and excel[2] == ["Excel", "hojas de cálculo", "spreadsheets", "Microsoft Excel"]
    tope = sum(construir_esco.MAX_SINONIMOS.values()) + sum(construir_esco.MAX_SINONIMOS_CORTOS.values())
    assert all(len(h[2]) <= tope for h in indice["h"])
    contable = next(o for o in indice["o"] if o[0] == "contable")
    assert contable[1] == "accountant" and contable[2] == ["contador", "contadora"]
    assert sorted(indice["h"][i][1] for i in contable[3]) == ["accounting", "apply tax legislation", "use spreadsheets software"]


def test_lee_zips_y_avisa_si_faltan_archivos(tmp_path):
    zip_es, zip_en = tmp_path / "ESCO dataset - v1.2.1 - classification - es - csv.zip", tmp_path / "en.zip"
    with zipfile.ZipFile(zip_es, "w") as z:
        for p in MUESTRA.glob("*_es.csv"):
            z.write(p, f"ESCO/{p.name}")
    with zipfile.ZipFile(zip_en, "w") as z:
        for p in MUESTRA.glob("*_en.csv"):
            z.write(p, p.name)
    r = construir_esco.construir([zip_es, zip_en], tmp_path / "esco.json")
    assert r["habilidades"] == 10 and r["ocupaciones"] == 4 and r["gzip"] < r["bytes"]
    assert json.loads((tmp_path / "esco.json").read_text(encoding="utf-8"))["fuente"] == "ESCO v1.2.1"
    with pytest.raises(FileNotFoundError, match="skills_en"):
        construir_esco.construir([zip_es], tmp_path / "otro.json")
    with pytest.raises(FileNotFoundError, match="--version"):  # sin versión en la ruta, no la inventa
        construir_esco.construir([MUESTRA], tmp_path / "otro.json")


# -- buscador -----------------------------------------------------------------------------------
@pytest.mark.parametrize("consulta", ["estadistica", "ESTADÍSTICA", "estadística", "Estadistica  "])
def test_busca_sin_importar_tildes_ni_mayusculas(esco, consulta):
    assert es(sg.buscar_habilidades(consulta, esco))[0] == "estadística"


def test_busca_en_ingles_y_en_sinonimos(esco):
    assert es(sg.buscar_habilidades("statistics", esco)) == ["estadística"]
    r = sg.buscar_habilidades("excel", esco)
    assert r[0] == {"es": "usar software de hojas de cálculo", "en": "use spreadsheets software", "sinonimo": "Excel"}
    assert sg.buscar_habilidades("bookkeep", esco)[0]["sinonimo"] == "bookkeeping"
    assert es(sg.buscar_habilidades("diseno grafico", esco)) == ["diseño gráfico"]


def test_orden_exacta_empieza_por_y_palabras(esco):
    # «SQL» exacto va antes que lo que solo empieza por «sql» o lo contiene.
    assert es(sg.buscar_habilidades("sql", esco))[0] == "SQL"
    # Todas las palabras, en cualquier orden y al inicio de palabra: «datos visual» → «visualización de datos».
    assert es(sg.buscar_habilidades("datos visual", esco)) == ["técnicas de presentación visual"]
    assert sg.buscar_habilidades("ual", esco) == []  # no busca a mitad de palabra


def test_minimo_dos_letras_y_maximo_ocho(esco, indice):
    assert sg.buscar_habilidades("e", esco) == [] and sg.buscar_habilidades("", esco) == []
    grande = sg.preparar_esco(indice | {"h": [[f"gestión {i}", f"management {i}", []] for i in range(30)]})
    assert len(sg.buscar_habilidades("gestion", grande)) == sg.MAX_RESULTADOS == 8


# -- ocupaciones de ESCO en las sugerencias ------------------------------------------------------
def test_tu_puesto_sugiere_la_ocupacion_y_sus_habilidades(esco):
    s = sg.sugerir({"puesto_actual": "Contador en una firma pequeña", "habilidades": ["contabilidad"]}, esco=esco)
    esco_roles = [r for r in s["roles"] if r["origen"] == "esco"]
    assert esco_roles == [{"rol": "Contable", "razon": "Ocupación de ESCO parecida a tu trabajo actual.", "origen": "esco"}]
    habs = [h["nombre"] for h in s["habilidades"] if h["origen"] == "esco"]
    assert "Aplicar la legislación tributaria" in habs and "Contabilidad" not in habs  # no repite lo que ya tienes


def test_tus_habilidades_sugieren_ocupaciones_que_las_piden(esco):
    s = sg.sugerir({"habilidades": ["Excel", "sql"]}, esco=esco)
    assert s["roles"] == [{"rol": "Analista de datos", "origen": "esco",
                           "razon": "Según ESCO, pide usar software de hojas de cálculo y SQL, que ya tienes."}]
    # las otras esenciales de esa ocupación, de la más usada a la menos usada
    assert [h["nombre"] for h in s["habilidades"]] == ["Estadística", "Python (programación informática)"]
    assert sg.sugerir({"habilidades": ["Excel"]}, esco=esco)["roles"] == []  # con una sola en común, no


def test_tus_roles_traen_sus_habilidades_esenciales(esco):
    s = sg.sugerir({"roles_objetivo": ["Diseñador gráfico"]}, esco=esco)
    assert [h["nombre"] for h in s["habilidades"]] == ["Técnicas de presentación visual", "Diseño gráfico"]
    assert s["roles"] == []  # ya lo elegiste: no se repite como sugerencia


def test_esco_comparte_turnos_y_no_duplica_roles_del_mapa(esco):
    s = sg.sugerir({"intereses": ["datos y análisis"], "habilidades": ["Excel", "SQL"]}, esco=esco)
    nombres = [sg.normalizar(r["rol"]) for r in s["roles"]]
    assert nombres.count("analista de datos") == 1 and s["roles"][0]["origen"] == "mapa"


# -- el navegador usa la misma lógica ---------------------------------------------------------
CONSULTAS = ["contador", "computadora", "excel", "Estadistica", "ESTADÍSTICA", "statistics", "diseno grafico", "datos visual", "sql", "e", "",
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
    assert len(datos["h"]) > 10000 and len(datos["o"]) > 2500
    assert sg.ESCO.stat().st_size < 3_000_000  # ~2.7 MB; ~0.7 MB con gzip
    esco = sg.cargar_esco()
    for consulta in ("contabilidad", "contabilidád", "accounting", "diseño gráfico", "diseno grafico", "python"):
        assert sg.buscar_habilidades(consulta, esco), consulta


def test_entiende_palabras_de_rd_aunque_esco_use_las_de_espana():
    esco = sg.cargar_esco()
    assert any("ordenador" in r["es"] for r in sg.buscar_habilidades("computadora", esco))
    assert any("marketing" in r["es"] for r in sg.buscar_habilidades("mercadeo", esco))
    assert any("contable" in r["es"] for r in sg.buscar_habilidades("contador", esco))
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
    assert FRASE in texto and "versión adaptada" in texto and "CC BY 4.0" in texto and "esco.ec.europa.eu" in html
    for readme, adaptada in (("README.md", "Versión adaptada"), ("README.en.md", "Adapted version")):
        t = (ROOT / readme).read_text(encoding="utf-8")
        assert FRASE in t and adaptada in t and "CC BY 4.0" in t and "esco.ec.europa.eu" in t


def test_cli_busca_habilidades():
    if not sg.ESCO.exists():
        pytest.skip("sin índice")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "perfil.py"), "buscar-habilidad", "contabilidad"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and json.loads(r.stdout), r.stderr
