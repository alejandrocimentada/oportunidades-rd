#!/usr/bin/env python3
"""Crea datos de DEMOSTRACIÓN (empresas y vacantes inventadas) en data/demo/, separados de tus datos.

Uso:
    python scripts/demo.py          # crea o reemplaza data/demo/
    python app.py --demo            # abre el tablero con esos datos
"""
from __future__ import annotations

import datetime as dt
import os
import shutil

from _comun import ROOT

DEMO_DIR = ROOT / "data" / "demo"

EMPRESAS = [
    ("Banco Quisqueya Digital (demo)", "banca", 90, "Está creando un equipo de analítica avanzada y automatización de procesos.",
     ["Head of Data", "Gerente de Innovación", "Director de Transformación Digital"]),
    ("TelcoCaribe (demo)", "telecomunicaciones", 85, "Usa chatbots en servicio al cliente; integra IA en sus canales.",
     ["Director de TI", "Head of Data & Analytics"]),
    ("Distribuidora del Cibao (demo)", "retail/distribución", 70, "Muchos procesos manuales de inventario y ventas: terreno ideal para automatizar.",
     ["Gerente de TI", "Gerente de Analítica"]),
    ("Seguros Atlántico (demo)", "seguros", 75, "Digitaliza reclamaciones; pide perfiles de IA aplicada.",
     ["Gerente de Transformación Digital", "Head of Data"]),
    ("LogiPuerto RD (demo)", "logística", 60, "Operación portuaria con datos de rastreo en tiempo real.",
     ["Gerente de Operaciones", "IT Manager"]),
    ("Zona Franca Textil Norte (demo)", "zona franca/manufactura", 45, "Mejora continua y calidad con visión por computadora.",
     ["Gerente de Mejora Continua"]),
]

VACANTES = [
    (0, "AI Integration Specialist", "Santo Domingo", "Me interesa",
     "Integrar modelos de lenguaje (LLM) y RAG en procesos de crédito. Python, SQL, APIs, Azure. Modalidad híbrida, "
     "lunes a viernes. 2 años de experiencia. Inglés avanzado. " * 2),
    (0, "Analista de Datos Senior", "Santo Domingo", "Aplicado",
     "Modelos de riesgo con Python y SQL, tableros en Power BI. 5 años de experiencia. Presencial. " * 2),
    (1, "Automation Engineer", "Santo Domingo · híbrido", "Entrevista",
     "Automate customer service workflows with Power Automate, Python and REST APIs. 3+ years of experience. Hybrid. " * 2),
    (1, "Chatbot Developer", "Santo Domingo", "Nuevo",
     "Desarrollar chatbots con LLM para WhatsApp. Python, Node, APIs, RAG. Híbrido. " * 3),
    (1, "Senior Network Engineer", "Santiago", "Descartado",
     "8+ years of experience with Cisco networks. On-site only, rotating shifts. " * 2),
    (2, "Especialista en Automatización (RPA)", "Santiago de los Caballeros", "Nuevo",
     "Automatizar procesos de inventario con UiPath y Power Automate. SQL. Presencial. Salario: RD$ 70,000. " * 2),
    (2, "Analista de BI", "Santo Domingo", "Contacté",
     "Tableros de ventas en Power BI y SQL, automatizar reportes con Python. Híbrido. " * 3),
    (3, "Ingeniero de IA Aplicada", "Santo Domingo", "Nuevo",
     "Integrar IA en reclamaciones: LLM, RAG, Python, Azure, MLOps. Remoto 2 días a la semana. 3 años de experiencia. " * 2),
    (3, "Científico de Datos", "Santo Domingo", "Rechazado",
     "Modelos actuariales, Python, PyTorch, estadística. Mínimo 6 años de experiencia. " * 2),
    (4, "Data Engineer", "Haina · híbrido", "Nuevo",
     "Pipelines de datos con Airflow, dbt y SQL sobre GCP. Python. Híbrido. " * 3),
    (5, "Ingeniero de Visión por Computadora", "Santiago", "Nuevo", "Visión por computadora para control de calidad."),
]


def main() -> int:
    os.environ["OPORTUNIDADES_RD_DATA"] = str(DEMO_DIR)
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    from oportunidades import ajuste, config, perfil as pf
    from oportunidades.db import Store
    from oportunidades.exportar import exportar
    from oportunidades import redaccion

    perfil = pf.importar(config.ROOT / "profile.example.yaml")
    with Store() as s:
        corrida = s.iniciar_corrida()
        emps = []
        for nombre, ind, interes, por_que, roles in EMPRESAS:
            slug = nombre.split(" (")[0].lower().replace(" ", "")
            emps.append(s.add_empresa(nombre, ind, f"https://{slug}.example", f"https://{slug}.example/empleos",
                                      por_que, interes, roles))
        for i, (ei, titulo, lugar, estado, desc) in enumerate(VACANTES):
            e = emps[ei]
            v, _ = s.upsert_vacante(titulo, e["id"], ubicacion=lugar, url=f"{e['url_empleos']}/{i + 1}",
                                    descripcion=desc.strip(), corrida_id=corrida if estado == "Nuevo" else None,
                                    fecha_publicacion=(dt.date.today() - dt.timedelta(days=i)).isoformat())
            r = ajuste.heuristica(perfil, dict(v, industria=e["industria"]))
            s.guardar_puntuacion(v["id"], r["ajuste"], r["por_que_encaja"], r["alertas"], r["faltantes"], r["puntuado_por"])
            camino = {"Me interesa": ["Me interesa"], "Aplicado": ["Me interesa", "Aplicado"],
                      "Contacté": ["Me interesa", "Aplicado", "Contacté"],
                      "Entrevista": ["Me interesa", "Aplicado", "Entrevista"],
                      "Rechazado": ["Me interesa", "Aplicado", "Rechazado"], "Descartado": ["Descartado"]}.get(estado, [])
            for paso in camino:
                s.cambiar_estado(v["id"], paso)
            if estado in ("Me interesa", "Entrevista"):
                redaccion.generar(s, perfil, v["id"])
        s.conn.execute("UPDATE empresas SET estado_rastreo = 'ok', ultimo_rastreo = ?", (dt.datetime.now().isoformat(timespec="seconds"),))
        s.conn.execute("UPDATE empresas SET estado_rastreo = 'abrir manualmente', nota_rastreo = ? WHERE nombre LIKE 'LogiPuerto%'",
                       ("La página necesita JavaScript para mostrar las vacantes.",))
        s.conn.execute("UPDATE empresas SET ats = 'greenhouse' WHERE nombre LIKE 'TelcoCaribe%'")
        s.terminar_corrida(corrida, {"manuales": [{"empresa": "LogiPuerto RD (demo)", "estado": "abrir manualmente",
                                                    "motivo": "La página necesita JavaScript para mostrar las vacantes.",
                                                    "enlace": "https://logipuertord.example/empleos"}],
                                     "ya_no_aparecen": []})
        print(f"Datos de demostración en {DEMO_DIR}")
        print(f"Excel: {exportar(s)}")
    print("Abre el tablero con: python app.py --demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
