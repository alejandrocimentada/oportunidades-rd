"""Mensaje de contacto y carta de presentación, solo para vacantes marcadas "Me interesa" (o más avanzadas).

Se guardan como archivos en data/documentos/<id>-<empresa>-<puesto>/. Nunca se envían solos:
tú los revisas, los copias y los envías.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import config, ia
from .db import ESTADOS_CON_DOCUMENTOS, DatosError, Store
from .texto import slug

TIPOS = ("mensaje", "carta")


def carpeta(vacante: dict) -> Path:
    path = config.docs_dir() / f"{vacante['id']}-{slug(vacante['empresa_nombre'], 25)}-{slug(vacante['titulo'], 35)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def puede_generar(vacante: dict) -> None:
    if vacante["estado"] not in ESTADOS_CON_DOCUMENTOS:
        raise DatosError(
            f"La vacante {vacante['id']} está en «{vacante['estado']}». Primero márcala «Me interesa» "
            "(los textos solo se preparan para las vacantes que eliges).")


SISTEMA_REDACTAR = """Redactas textos para postularse a empleos en la República Dominicana. Escribe en el idioma
indicado, en primera persona, con tono profesional y cercano, sin exagerar ni inventar experiencia,
títulos, cifras ni datos que no estén en el perfil. Devuelve solo el texto final, sin comentarios."""

INSTRUCCIONES = {
    "mensaje": {"es": "Escribe un mensaje corto (máximo 90 palabras) para LinkedIn o correo, dirigido a "
                      "alguien del área (sin nombre: usa un saludo general). Menciona el puesto, 1-2 razones "
                      "concretas de encaje y pide una conversación breve.",
                "en": "Write a short message (max 90 words) for LinkedIn or email, addressed to someone in "
                      "the team (no name: use a general greeting). Mention the role, 1-2 concrete reasons "
                      "you fit and ask for a brief conversation."},
    "carta": {"es": "Escribe una carta de presentación de 250-350 palabras para esta vacante.",
              "en": "Write a 250-350 word cover letter for this role."},
}


def _prompt(perfil: dict, vacante: dict, tipo: str, idioma: str) -> str:
    import json
    return (INSTRUCCIONES[tipo][idioma] + "\n\nPERFIL:\n" +
            json.dumps(ia.perfil_para_ia(perfil), ensure_ascii=False, indent=2) +
            "\n\nVACANTE:\n" + json.dumps({k: vacante.get(k, "") for k in
                                          ("titulo", "empresa_nombre", "ubicacion", "descripcion")},
                                         ensure_ascii=False, indent=2) +
            "\n\nPOR QUÉ ENCAJA:\n- " + "\n- ".join(vacante.get("por_que_encaja") or []))


def plantilla(perfil: dict, vacante: dict, tipo: str, idioma: str) -> str:
    """Borrador básico sin IA. Edítalo antes de usarlo."""
    nombre = perfil.get("nombre") or ("[Tu nombre]" if idioma == "es" else "[Your name]")
    habilidades = ", ".join(perfil.get("habilidades", [])[:4])
    razones = [r.rstrip(".") for r in (vacante.get("por_que_encaja") or [])][:2]
    enlaces = " · ".join(v for v in (perfil.get("enlaces") or {}).values() if v)
    puesto, empresa = vacante["titulo"], vacante["empresa_nombre"] or "su empresa"
    if tipo == "mensaje":
        if idioma == "en":
            return (f"Hello, I saw the {puesto} opening at {empresa} and I'm very interested. "
                    f"I work with {habilidades}, and {perfil.get('titular') or 'I focus on applied AI and automation'}. "
                    f"Would you have 15 minutes for a short conversation about the role?\n\nThank you,\n{nombre}"
                    + (f"\n{enlaces}" if enlaces else ""))
        return (f"Hola, vi la vacante de {puesto} en {empresa} y me interesa mucho. "
                f"Trabajo con {habilidades}"
                + (f" y {perfil['titular'][0].lower() + perfil['titular'][1:]}" if perfil.get("titular") else "")
                + ". ¿Tendría 15 minutos para conversar brevemente sobre el puesto?\n\nGracias,\n" + nombre
                + (f"\n{enlaces}" if enlaces else ""))
    fecha = dt.date.today().strftime("%d/%m/%Y")
    if idioma == "en":
        cuerpo = [f"Santo Domingo, {fecha}", "", "Dear Hiring Team,", "",
                  f"I am writing to apply for the {puesto} position at {empresa}.",
                  perfil.get("experiencia", ""), ""]
        if razones:
            cuerpo += ["Why I think I am a good fit:"] + [f"- {r}." for r in razones] + [""]
        cuerpo += [f"My main skills include {habilidades}. I would welcome the opportunity to discuss how I "
                   f"can contribute to your team.", "", "Sincerely,", nombre] + ([enlaces] if enlaces else [])
    else:
        cuerpo = [f"Santo Domingo, {fecha}", "", "Estimado equipo de selección:", "",
                  f"Les escribo para postularme a la posición de {puesto} en {empresa}.",
                  perfil.get("experiencia", ""), ""]
        if razones:
            cuerpo += ["Por qué creo que encajo:"] + [f"- {r}." for r in razones] + [""]
        cuerpo += [f"Entre mis habilidades principales están {habilidades}. Me encantaría conversar sobre "
                   "cómo puedo aportar a su equipo.", "", "Atentamente,", nombre] + ([enlaces] if enlaces else [])
    return "\n".join(cuerpo).replace("\n\n\n", "\n\n")


def generar(store: Store, perfil: dict, vacante_id: int, tipos=TIPOS, idioma: str | None = None,
            llamadas: dict | None = None) -> dict[str, Path]:
    vac = store.get_vacante(vacante_id)
    if not vac:
        raise DatosError(f"No existe la vacante {vacante_id}.")
    puede_generar(vac)
    idioma = idioma or vac["idioma"] or "es"
    usar_ia = ia.disponible(perfil)
    out = {}
    for tipo in tipos:
        if usar_ia:
            texto = ia.completar(perfil, SISTEMA_REDACTAR, _prompt(perfil, vac, tipo, idioma), llamadas).strip()
            origen = ia.proveedor(perfil)
        else:
            texto = plantilla(perfil, vac, tipo, idioma)
            origen = "plantilla básica: edítala antes de usarla"
        out[tipo] = guardar_texto(store, vac, tipo, texto, origen)
    return out


def guardar_texto(store: Store, vac: dict, tipo: str, texto: str, origen: str = "agente") -> Path:
    if tipo not in TIPOS:
        raise DatosError(f"Tipo inválido: {tipo}. Usa: {', '.join(TIPOS)}")
    puede_generar(vac)
    path = carpeta(vac) / f"{tipo}.md"
    path.write_text(f"<!-- {tipo} · {vac['titulo']} · {vac['empresa_nombre']} · generado por {origen} · "
                    f"{dt.date.today().isoformat()} · NO se envía solo -->\n\n{texto.strip()}\n", encoding="utf-8")
    store.guardar_documento(vac["id"], tipo, path)
    return path


def leer(path: str | Path | None) -> str:
    if not path or not Path(path).exists():
        return ""
    texto = Path(path).read_text(encoding="utf-8")
    if texto.startswith("<!--"):
        texto = texto.split("-->", 1)[1]
    return texto.strip()
