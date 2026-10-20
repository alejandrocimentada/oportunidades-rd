#!/usr/bin/env python3
"""Crea datos de DEMOSTRACIÓN (empresas inventadas) en data/demo/, separados de tus datos.

Uso:
    python scripts/demo.py          # crea o reemplaza data/demo/
    python app.py --demo            # abre el tablero con esos datos
"""
from __future__ import annotations

import os
import shutil

from _comun import ROOT

DEMO_DIR = ROOT / "data" / "demo"


def _empresa(nombre, tipo, industria, presencia, equipos, roles, razones, alertas, contactos, estado):
    slug = nombre.split(" (")[0].lower().replace(" ", "")
    web = f"https://{slug}.example"
    return estado, {
        "nombre": nombre, "tipo": tipo, "industria": industria, "sitio_web": web, "presencia_rd": presencia,
        "fuentes_presencia": [{"titulo": "Página institucional (demo)", "url": f"{web}/republica-dominicana"}],
        "equipos": equipos, "roles": [{"rol": r, "razon": z} for r, z in roles],
        "evidencia": [{"texto": f"Vacante pasada de {roles[0][0]} en Santo Domingo (demo)", "url": f"{web}/empleos/123"}],
        "razones": razones, "alertas": alertas, "url_empleos": f"{web}/empleos",
        "portal_rd": f"{web}/empleos?pais=DO", "talento": f"{web}/talento", "roles_contacto": contactos,
    }


EMPRESAS = [
    _empresa("Distribuidora del Caribe (demo)", "grupo local", "retail/distribución",
             "Sede y centro de distribución en Santo Domingo.",
             ["Supply chain / planificación de demanda", "BI y analítica", "Transformación digital"],
             [("Supply Chain Analyst con enfoque en automatización", "Planificación de demanda con SAP y Excel."),
              ("BI Analyst", "Tableros en Tableau y automatización de reportes.")],
             ["Consumo masivo con mucha planificación manual.", "Usa SAP, que ya conoces.", "Equipo de BI en crecimiento."],
             ["Algunos roles de supply chain son presenciales."], ["Gerente de Supply Chain", "Gerente de Analítica"],
             "Me interesa"),
    _empresa("Servicios Globales RD (demo)", "multinacional", "tecnología/consultoría",
             "Centro de servicios compartidos para Latinoamérica en Santo Domingo.",
             ["Automatización de procesos (RPA)", "ERP / SAP"],
             [("Automation Specialist", "Automatizas procesos con Python y APIs."),
              ("SAP Functional Analyst", "Experiencia de usuario avanzado en SAP.")],
             ["Centro con procesos en inglés y español.", "Programa activo de automatización.", "Modalidad híbrida."],
             ["Pide inglés avanzado para todas las posiciones."], ["Talent Acquisition", "Gerente de Automatización"],
             "Contacté"),
    _empresa("Banco Quisqueya Digital (demo)", "grupo local", "banca",
             "Oficinas principales en Santo Domingo.",
             ["Transformación digital / innovación", "Datos y analítica"],
             [("Digital Transformation Specialist", "Integras herramientas con APIs y automatizas tareas.")],
             ["Laboratorio de innovación propio.", "Integra pagos y APIs.", "Banca es una de tus industrias."],
             [], ["Gerente de Innovación", "Head of Data"], "Descubierta"),
    _empresa("Zona Franca Norte Médica (demo)", "multinacional", "zona franca/manufactura",
             "Planta de dispositivos médicos en zona franca.",
             ["Planificación y supply chain", "Mejora continua"],
             [("Demand Planner", "Tu experiencia directa como Demand Planner.")],
             ["Planta grande con equipo de planificación local.", "Procesos medibles y regulados.", "Estabilidad."],
             ["Mayormente presencial en planta.", "Algunos roles por turnos."], ["Gerente de Supply Chain"],
             "Descubierta"),
]


def main() -> int:
    os.environ["OPORTUNIDADES_RD_DATA"] = str(DEMO_DIR)
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    from oportunidades import config, perfil as pf, redaccion
    from oportunidades.db import Store
    from oportunidades.exportar import exportar

    perfil = pf.importar(config.ROOT / "profile.example.yaml")
    caminos = {"Me interesa": ["Me interesa"], "Contacté": ["Me interesa", "Investigando", "Contacté"]}
    with Store() as s:
        for estado, data in EMPRESAS:
            e, _ = s.guardar_empresa(data)
            for paso in caminos.get(estado, []):
                s.cambiar_estado(e["id"], paso)
            if estado != "Descubierta":
                redaccion.generar(s, perfil, e["id"])
        corrida = s.iniciar_corrida()
        primera = s.get_empresa(1)
        s.upsert_vacante("Analista de Planificación (demo)", primera["id"], ubicacion="Santo Domingo",
                         url=f"{primera['url_empleos']}/1", corrida_id=corrida)
        s.conn.execute("UPDATE empresas SET estado_rastreo = 'sin vacantes'")
        s.conn.execute("UPDATE empresas SET estado_rastreo = 'ok' WHERE id = ?", (primera["id"],))
        s.terminar_corrida(corrida, {"manuales": [], "ya_no_aparecen": []})
        print(f"Datos de demostración en {DEMO_DIR}")
        print(f"Excel: {exportar(s)}")
    print("Abre el tablero con: python app.py --demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
