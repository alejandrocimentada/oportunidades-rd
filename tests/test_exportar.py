from openpyxl import load_workbook

from oportunidades import config
from oportunidades.db import Store
from oportunidades.exportar import COLORES_ESTADO, exportar, exportar_seguro


def _datos(store):
    e = store.add_empresa("Banco Ejemplo", "banca", "https://b.do", "https://b.do/empleos", "Equipo de datos",
                          85, ["Head of Data"])
    v, _ = store.upsert_vacante("Analista de Datos", e["id"], url="https://b.do/empleos/1")
    store.guardar_puntuacion(v["id"], 77, ["a"], ["b"], ["c"], "heurística")
    store.cambiar_estado(v["id"], "Me interesa")
    store.cambiar_estado(v["id"], "Aplicado")
    store.upsert_vacante("Ejecutivo", e["id"])


def test_xlsx_con_hojas_filtros_encabezados_fijos_y_colores(store):
    _datos(store)
    path = exportar(store)
    assert path == config.xlsx_path() and path.exists()
    wb = load_workbook(path)
    assert wb.sheetnames == ["Resumen", "Empresas", "Vacantes", "Seguimiento"]
    for ws in wb.worksheets:
        assert ws.freeze_panes == "A2"
        assert ws.auto_filter.ref
        assert ws["A1"].font.bold
    vac = wb["Vacantes"]
    filas = {r[2].value: r for r in vac.iter_rows(min_row=2)}
    assert filas["Analista de Datos"][3].value == "Aplicado"
    assert filas["Analista de Datos"][3].fill.fgColor.rgb.endswith(COLORES_ESTADO["Aplicado"])
    assert filas["Analista de Datos"][4].value == 77
    seg = [(r[4].value, r[5].value) for r in wb["Seguimiento"].iter_rows(min_row=2)]
    assert ("Me interesa", "Aplicado") in seg and ("Nuevo", "Me interesa") in seg
    emp = list(wb["Empresas"].iter_rows(min_row=2, values_only=True))[0]
    assert emp[0] == "Banco Ejemplo" and "Head of Data" in emp[10] and "linkedin.com/search" in emp[11]
    resumen = {r[0]: r[1] for r in wb["Resumen"].iter_rows(min_row=2, values_only=True) if r[0]}
    assert resumen["Aplicado"] == 1 and resumen["Nuevo"] == 1 and resumen["Aplicaciones esta semana"] == 1


def test_se_regenera_despues_de_cada_cambio():
    with Store(after_change=lambda s: exportar_seguro(s)) as s:
        s.add_empresa("Telco Ejemplo", "telecomunicaciones")
        assert config.xlsx_path().exists()
        antes = config.xlsx_path().stat().st_mtime_ns
        v, _ = s.upsert_vacante("Analista", empresa_nombre="Telco Ejemplo")
        s.cambiar_estado(v["id"], "Me interesa")
        assert config.xlsx_path().stat().st_mtime_ns >= antes
        estados = [r[3] for r in load_workbook(config.xlsx_path())["Vacantes"].iter_rows(min_row=2, values_only=True)]
        assert estados == ["Me interesa"]


def test_excel_abierto_no_rompe(store, monkeypatch):
    import oportunidades.exportar as ex

    def bloqueado(*a, **k):
        raise PermissionError("abierto")
    monkeypatch.setattr(ex, "exportar", bloqueado)
    assert "abierto en Excel" in ex.exportar_seguro(store)
