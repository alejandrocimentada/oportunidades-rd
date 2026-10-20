"""Mensaje de contacto y carta de postulación general, solo para empresas que marcaste «Me interesa»
(o más avanzadas en el seguimiento).

Se adaptan al equipo que encaja y al rol probable de esa empresa, y enlazan a tu trabajo publicado
(portafolio, GitHub). Se guardan como archivos en data/documentos/<id>-<empresa>/. Nunca se envían
solos: tú los revisas, los copias y los envías.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import config, ia
from .db import ESTADOS_CON_DOCUMENTOS, DatosError, Store
from .texto import slug

TIPOS = ("mensaje", "carta")


def carpeta(empresa: dict) -> Path:
    path = config.docs_dir() / f"{empresa['id']}-{slug(empresa['nombre'], 40)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def puede_generar(empresa: dict) -> None:
    if empresa["estado"] not in ESTADOS_CON_DOCUMENTOS:
        raise DatosError(
            f"«{empresa['nombre']}» está en «{empresa['estado']}». Primero márcala «Me interesa» "
            "(los textos solo se preparan para las empresas que eliges).")


def enfoque(empresa: dict, rol: str | None = None) -> tuple[str, str, str]:
    """(rol probable, razón, equipo) en el que se centra el texto."""
    roles = empresa.get("roles") or []
    elegido = next((r for r in roles if rol and r["rol"].lower() == rol.lower()), None) or \
        (roles[0] if roles else {"rol": rol or "", "razon": ""})
    equipos = empresa.get("equipos") or []
    return elegido["rol"], elegido.get("razon", ""), equipos[0] if equipos else ""


def enlaces_trabajo(perfil: dict) -> list[str]:
    """Trabajo publicado primero (portafolio, GitHub), luego LinkedIn."""
    e = perfil.get("enlaces") or {}
    return [e[k] for k in ("portafolio", "github", "linkedin") if e.get(k)]


SISTEMA_REDACTAR = """Redactas textos para buscar trabajo en la República Dominicana. Escribe en el idioma
indicado, en primera persona, con tono profesional y cercano, sin exagerar ni inventar experiencia,
títulos, cifras ni datos que no estén en el perfil o en la información de la empresa. No hay una
vacante concreta: es un acercamiento al equipo. Devuelve solo el texto final, sin comentarios."""

INSTRUCCIONES = {
    "mensaje": {"es": "Escribe un mensaje corto (máximo 90 palabras) para LinkedIn o correo, dirigido a alguien del "
                      "equipo indicado (sin nombre: usa un saludo general). Menciona el equipo y el tipo de rol, 1-2 "
                      "razones concretas de encaje, incluye el enlace a mi trabajo y pide una conversación breve.",
                "en": "Write a short message (max 90 words) for LinkedIn or email, addressed to someone in the given "
                      "team (no name: use a general greeting). Mention the team and the kind of role, 1-2 concrete "
                      "reasons I fit, include the link to my work and ask for a brief conversation."},
    "carta": {"es": "Escribe una carta de postulación general de 250-350 palabras (no responde a una vacante "
                    "publicada) para el equipo y el rol indicados. Termina con los enlaces a mi trabajo.",
              "en": "Write a 250-350 word general application letter (not answering a posted opening) for the "
                    "given team and role. End with the links to my work."},
}


def _prompt(perfil: dict, empresa: dict, tipo: str, idioma: str, rol: str | None) -> str:
    rol_txt, razon, equipo = enfoque(empresa, rol)
    datos = {"empresa": empresa["nombre"], "presencia_en_rd": empresa.get("presencia_rd", ""),
             "equipo": equipo, "rol_probable": rol_txt, "razon_del_rol": razon,
             "por_que_encaja": empresa.get("razones") or [], "enlaces_a_mi_trabajo": enlaces_trabajo(perfil)}
    return (INSTRUCCIONES[tipo][idioma] + "\n\nPERFIL:\n" + json.dumps(ia.perfil_para_ia(perfil), ensure_ascii=False,
                                                                      indent=2) +
            "\n\nEMPRESA:\n" + json.dumps(datos, ensure_ascii=False, indent=2))


def plantilla(perfil: dict, empresa: dict, tipo: str, idioma: str, rol: str | None = None) -> str:
    """Borrador básico sin IA. Edítalo antes de usarlo."""
    nombre = perfil.get("nombre") or ("[Tu nombre]" if idioma == "es" else "[Your name]")
    habilidades = ", ".join(perfil.get("habilidades", [])[:4])
    rol_txt, razon_rol, equipo = enfoque(empresa, rol)
    razon_rol = razon_rol.rstrip(".")
    razones = [r.rstrip(".") for r in (empresa.get("razones") or [])][:2]
    enlaces = enlaces_trabajo(perfil)
    emp = empresa["nombre"]
    if idioma == "en":
        area = f"the {equipo} team" if equipo else "your team"
        foco = f" in a role like {rol_txt}" if rol_txt else ""
        if tipo == "mensaje":
            return (f"Hello, I'm interested in contributing to {area} at {emp}{foco}. I work with {habilidades}."
                    + (f" Relevant experience: {razon_rol[0].lower() + razon_rol[1:]}." if razon_rol else "")
                    + (f" You can see my work here: {enlaces[0]}." if enlaces else "")
                    + f" Would you have 15 minutes for a short conversation?\n\nThank you,\n{nombre}")
        cuerpo = [f"Santo Domingo, {dt.date.today():%d/%m/%Y}", "", "Dear Hiring Team,", "",
                  f"I am writing to express my interest in joining {area} at {emp}{foco}.",
                  perfil.get("experiencia", ""), ""]
        if razones:
            cuerpo += [f"Why {emp}:"] + [f"- {r}." for r in razones] + [""]
        cuerpo += [f"My main skills include {habilidades}. I would welcome a conversation about current or future "
                   "opportunities on your team.", ""]
        cuerpo += (["You can see my work here:"] + enlaces + [""]) if enlaces else []
        cuerpo += ["Sincerely,", nombre]
    else:
        al_area = f"al equipo de {equipo}" if equipo else "a su equipo"
        del_area = f"del equipo de {equipo}" if equipo else "de su equipo"
        foco = f", en un rol como {rol_txt}" if rol_txt else ""
        if tipo == "mensaje":
            return (f"Hola, me interesa aportar {al_area} de {emp}{foco}. Trabajo con {habilidades}."
                    + (f" Experiencia relevante: {razon_rol[0].lower() + razon_rol[1:]}." if razon_rol else "")
                    + (f" Puede ver mi trabajo aquí: {enlaces[0]}." if enlaces else "")
                    + f" ¿Tendría 15 minutos para conversar brevemente?\n\nGracias,\n{nombre}")
        cuerpo = [f"Santo Domingo, {dt.date.today():%d/%m/%Y}", "", "Estimado equipo:", "",
                  f"Les escribo para expresar mi interés en formar parte {del_area} en {emp}{foco}.",
                  perfil.get("experiencia", ""), ""]
        if razones:
            cuerpo += [f"Por qué me interesa {emp}:"] + [f"- {r}." for r in razones] + [""]
        cuerpo += [f"Entre mis habilidades principales están {habilidades}. Me encantaría conversar sobre "
                   "oportunidades actuales o futuras en su equipo.", ""]
        cuerpo += (["Pueden ver mi trabajo aquí:"] + enlaces + [""]) if enlaces else []
        cuerpo += ["Atentamente,", nombre]
    return "\n".join(cuerpo).replace("\n\n\n", "\n\n")


def generar(store: Store, perfil: dict, empresa_id: int, tipos=TIPOS, idioma: str | None = None,
            rol: str | None = None, llamadas: dict | None = None) -> dict[str, Path]:
    emp = store.get_empresa(empresa_id)
    if not emp:
        raise DatosError(f"No existe la empresa {empresa_id}.")
    puede_generar(emp)
    idioma = idioma or "es"
    usar_ia = ia.disponible(perfil)
    out = {}
    for tipo in tipos:
        if usar_ia:
            texto = ia.completar(perfil, SISTEMA_REDACTAR, _prompt(perfil, emp, tipo, idioma, rol), llamadas).strip()
            origen = ia.proveedor(perfil)
        else:
            texto = plantilla(perfil, emp, tipo, idioma, rol)
            origen = "plantilla básica: edítala antes de usarla"
        out[tipo] = guardar_texto(store, emp, tipo, texto, origen)
    return out


def guardar_texto(store: Store, empresa: dict, tipo: str, texto: str, origen: str = "agente") -> Path:
    if tipo not in TIPOS:
        raise DatosError(f"Tipo inválido: {tipo}. Usa: {', '.join(TIPOS)}")
    puede_generar(empresa)
    path = carpeta(empresa) / f"{tipo}.md"
    path.write_text(f"<!-- {tipo} · {empresa['nombre']} · generado por {origen} · {dt.date.today().isoformat()} · "
                    f"NO se envía solo -->\n\n{texto.strip()}\n", encoding="utf-8")
    store.guardar_documento(empresa["id"], tipo, path)
    return path


def leer(path: str | Path | None) -> str:
    if not path or not Path(path).exists():
        return ""
    texto = Path(path).read_text(encoding="utf-8")
    if texto.startswith("<!--"):
        texto = texto.split("-->", 1)[1]
    return texto.strip()
