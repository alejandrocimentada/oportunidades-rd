"""Exporta todo a data/oportunidades.xlsx: Resumen, Empresas, Vacantes, Seguimiento."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config
from .contactos import contactos
from .db import ESTADOS, Store

VERDE = "9BE28F"
COLORES_ESTADO = {
    "Nuevo": "E8EEF2", "Me interesa": "D6F5D0", "Aplicado": "C9E7FF", "Contacté": "E3D9FF",
    "Entrevista": "FFE8B3", "Oferta": "9BE28F", "Rechazado": "F8D0D0", "Descartado": "E0E0E0",
}
_ENCABEZADO = PatternFill("solid", fgColor=VERDE)


def _hoja(wb: Workbook, titulo: str, columnas: list[tuple[str, int]], filas: list[list],
          col_estado: int | None = None, primera: bool = False):
    ws = wb.active if primera else wb.create_sheet()
    ws.title = titulo
    ws.append([c for c, _ in columnas])
    for i, (_, ancho) in enumerate(columnas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
        cell = ws.cell(row=1, column=i)
        cell.font, cell.fill = Font(bold=True, color="1B1F23"), _ENCABEZADO
    for fila in filas:
        ws.append(fila)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=isinstance(cell.value, str) and len(cell.value) > 40)
            if isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink, cell.style = cell.value, "Hyperlink"
        if col_estado is not None:
            c = row[col_estado]
            if c.value in COLORES_ESTADO:
                c.fill = PatternFill("solid", fgColor=COLORES_ESTADO[c.value])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def exportar(store: Store, destino: Path | None = None) -> Path:
    destino = destino or config.xlsx_path()
    r = store.resumen()
    wb = Workbook()

    filas = [[e, r["por_estado"][e]] for e in ESTADOS]
    filas += [[], ["Total de vacantes", r["total_vacantes"]], ["Empresas", r["total_empresas"]],
              ["Aplicaciones esta semana", r["aplicadas_semana"]], ["Sin puntuar", r["sin_puntuar"]],
              ["Último rastreo", (r["ultima_corrida"] or {}).get("fin", "")]]
    if r["seguimientos"]:
        filas += [[], ["Seguimientos próximos", ""]]
        filas += [[f"{s['seguimiento']} · {s['empresa_nombre']}", s["titulo"]] for s in r["seguimientos"]]
    _hoja(wb, "Resumen", [("Estado", 34), ("Cantidad", 40)], filas, col_estado=0, primera=True)

    filas = []
    for e in store.empresas():
        cts = contactos(e)
        filas.append([e["nombre"], e["industria"], e["interes"], e["por_que"], e["sitio_web"], e["url_empleos"],
                      e["estado_rastreo"], e["nota_rastreo"], e["ats"], e["ultimo_rastreo"],
                      "; ".join(c["rol"] for c in cts), "\n".join(c["linkedin"] for c in cts)])
    _hoja(wb, "Empresas", [("Empresa", 26), ("Industria", 20), ("Interés", 9), ("Por qué", 50), ("Sitio web", 30),
                           ("Página de empleos", 34), ("Rastreo", 18), ("Nota de rastreo", 34), ("ATS", 14),
                           ("Último rastreo", 20), ("Roles a contactar", 40), ("Búsqueda LinkedIn", 60)], filas)

    filas = [[v["id"], v["empresa_nombre"], v["titulo"], v["estado"], v["ajuste"], v["ubicacion"], v["url"],
              v["fecha_publicacion"], v["fuente"], v["idioma"], "\n".join(v["por_que_encaja"]),
              "\n".join(v["alertas"]), "\n".join(v["faltantes"]), v["nota"], v["seguimiento"],
              "sí" if v["activa"] else "ya no aparece", v["primera_vez"][:10], v["mensaje_path"], v["carta_path"]]
             for v in store.vacantes()]
    _hoja(wb, "Vacantes", [("ID", 6), ("Empresa", 24), ("Puesto", 36), ("Estado", 14), ("Ajuste", 8),
                           ("Ubicación", 20), ("Enlace", 40), ("Publicada", 12), ("Fuente", 16), ("Idioma", 8),
                           ("Por qué encaja", 50), ("Señales de alerta", 50), ("Lo que me falta", 36),
                           ("Notas", 30), ("Seguimiento", 12), ("Activa", 12), ("Encontrada", 12),
                           ("Mensaje", 30), ("Carta", 30)], filas, col_estado=3)

    filas = [[h["fecha"].replace("T", " "), h["vacante_id"], h["empresa_nombre"], h["titulo"], h["de_estado"],
              h["a_estado"], h["nota"]] for h in store.historial()]
    _hoja(wb, "Seguimiento", [("Fecha", 20), ("Vacante", 9), ("Empresa", 24), ("Puesto", 36), ("De", 14),
                              ("A", 14), ("Nota", 40)], filas, col_estado=5)

    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino


def exportar_seguro(store: Store) -> str:
    """Para usar después de cada cambio: si el Excel está abierto (Windows lo bloquea), avisa y sigue."""
    try:
        return str(exportar(store))
    except PermissionError:
        return "No se pudo actualizar oportunidades.xlsx (¿está abierto en Excel?). Ciérralo y corre scripts/exportar.py."
