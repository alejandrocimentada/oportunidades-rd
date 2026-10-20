#!/usr/bin/env python3
"""Crea datos de DEMOSTRACIÓN (empresas inventadas) en data/demo/, separados de tus datos.

Uso:
    python scripts/demo.py          # crea o reemplaza data/demo/
    python app.py --demo            # abre el tablero con esos datos

Las empresas encajan con el perfil de ejemplo (profile.example.yaml, «Ana Ejemplo»). La demo pública
(scripts/construir_demo.py) usa estos mismos datos.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

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
             ["Automatización de procesos", "BI y analítica", "Transformación digital"],
             [("Especialista en automatización", "3 años automatizando reportes y procesos en distribución."),
              ("Analista de datos", "Tableros de ventas en Power BI con SQL.")],
             ["Es la misma industria en la que ya trabajas.", "Usa Power BI y Power Automate.",
              "Equipo de transformación digital en crecimiento."],
             ["Algunos roles son presenciales en el centro de distribución."],
             ["Gerente de Transformación Digital", "Talent Acquisition"], "Me interesa"),
    _empresa("Servicios Globales RD (demo)", "multinacional", "tecnología/consultoría",
             "Centro de servicios compartidos para Latinoamérica en Santo Domingo.",
             ["Automatización de procesos (RPA)", "IA aplicada"],
             [("Automation Specialist", "Automatizas procesos con Python y Power Automate."),
              ("AI Integration Specialist", "Construiste un asistente interno con IA para consultar inventario.")],
             ["Centro con procesos en inglés y español.", "Programa activo de automatización.", "Modalidad híbrida."],
             ["Las reuniones con clientes son en inglés."], ["Talent Acquisition", "Gerente de Automatización"],
             "Contacté"),
    _empresa("Banco Quisqueya Digital (demo)", "grupo local", "banca",
             "Oficinas principales en Santo Domingo.",
             ["Transformación digital / innovación", "Datos y analítica"],
             [("AI Integration Specialist", "Integras LLM, RAG y APIs en procesos de negocio."),
              ("Analista de datos", "SQL y Power BI para reportes de gestión.")],
             ["Laboratorio de innovación propio.", "Integra pagos y APIs.", "Banca es una de tus industrias."],
             [], ["Gerente de Innovación", "Head of Data"], "Descubierta"),
    _empresa("Telecom Antillas (demo)", "multinacional", "telecomunicaciones",
             "Operación y centro de atención al cliente en Santo Domingo.",
             ["Atención digital / chatbots", "Datos y analítica"],
             [("Ingeniero de IA aplicada", "Tu asistente con IA y RAG es el tipo de proyecto que hacen."),
              ("Analista de datos", "Automatizas reportes con Python y SQL.")],
             ["Telecomunicaciones es una de tus industrias.", "Equipo local de canales digitales.",
              "Dos días remotos por semana."],
             ["Algunas vacantes piden Azure, que no está en tu perfil."], ["Gerente de Canales Digitales"],
             "Entrevista"),
    _empresa("LogiPuerto RD (demo)", "empresa local en crecimiento", "logística",
             "Operador logístico con almacenes en Santo Domingo Este y Haina.",
             ["Datos y analítica", "Mejora de procesos"],
             [("Analista de datos", "Tableros en Power BI y reportes automatizados.")],
             ["Logística es una de tus industrias.", "Empresa en crecimiento, con mucho por automatizar.",
              "Conoces la operación de distribución."],
             ["Horario extendido en temporada alta."], ["Gerente de Operaciones"], "Aplicado"),
    _empresa("Nube Taína Labs (demo)", "tecnología/startup", "tecnología/consultoría",
             "Startup con oficina en Santo Domingo que hace software para pymes.",
             ["Producto / IA", "Integraciones"],
             [("AI Integration Specialist", "LLM, RAG y APIs en un producto real.")],
             ["Producto con IA desde el primer día.", "Equipo pequeño: mucho aprendizaje.", "Trabajo remoto."],
             ["El salario publicado está por debajo de tu mínimo."], ["Fundador / CTO"], "Descubierta"),
]

# Estados intermedios por los que pasa cada empresa (el historial muestra una fecha en cada paso).
CAMINOS = {
    "Me interesa": ["Me interesa"],
    "Contacté": ["Me interesa", "Investigando", "Contacté"],
    "Aplicado": ["Me interesa", "Aplicado"],
    "Entrevista": ["Me interesa", "Investigando", "Aplicado", "Entrevista"],
}
VACANTES = {
    "Distribuidora del Caribe (demo)": ["Analista de Automatización (demo)", "Analista de Planificación (demo)"],
    "Telecom Antillas (demo)": ["Ingeniero de IA Conversacional (demo)"],
}
MANUAL = ("Nube Taína Labs (demo)", "abrir manualmente", "La página de empleos necesita JavaScript.")


def crear_datos(destino: Path = DEMO_DIR) -> Path:
    """Crea (o reemplaza) la base de demostración en `destino` y devuelve la ruta del Excel."""
    os.environ["OPORTUNIDADES_RD_DATA"] = str(destino)
    if destino.exists():
        shutil.rmtree(destino)
    from oportunidades import config, perfil as pf, redaccion
    from oportunidades.db import Store
    from oportunidades.exportar import exportar

    perfil = pf.importar(config.ROOT / "profile.example.yaml")
    with Store() as s:
        ids = {}
        for estado, data in EMPRESAS:
            e, _ = s.guardar_empresa(data)
            ids[e["nombre"]] = e["id"]
            for paso in CAMINOS.get(estado, []):
                s.cambiar_estado(e["id"], paso)
            if estado != "Descubierta":
                redaccion.generar(s, perfil, e["id"])
        corrida = s.iniciar_corrida()
        s.conn.execute("UPDATE empresas SET estado_rastreo = 'sin vacantes'")
        for nombre, titulos in VACANTES.items():
            e = s.get_empresa(ids[nombre])
            for i, titulo in enumerate(titulos, 1):
                s.upsert_vacante(titulo, e["id"], ubicacion="Santo Domingo", url=f"{e['url_empleos']}/{i}",
                                 corrida_id=corrida)
            s.conn.execute("UPDATE empresas SET estado_rastreo = 'ok' WHERE id = ?", (e["id"],))
        nombre, estado, motivo = MANUAL
        manual = s.get_empresa(ids[nombre])
        s.conn.execute("UPDATE empresas SET estado_rastreo = ?, nota_rastreo = ? WHERE id = ?",
                       (estado, motivo, manual["id"]))
        s.terminar_corrida(corrida, {"ya_no_aparecen": [], "manuales": [
            {"empresa": nombre, "estado": estado, "motivo": motivo, "enlace": manual["url_empleos"]}]})
        return exportar(s)


def main() -> int:
    xlsx = crear_datos()
    print(f"Datos de demostración en {DEMO_DIR}")
    print(f"Excel: {xlsx}")
    print("Abre el tablero con: python app.py --demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
