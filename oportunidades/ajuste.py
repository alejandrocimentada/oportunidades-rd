"""Puntuación de ajuste (0-100) de una vacante contra el perfil.

Hay dos formas:
- `heuristica()`: reglas simples, sin internet ni IA. Siempre disponible; es un primer filtro.
- La IA (Claude u OpenAI, ver ia.py) o el propio agente (SKILL.md) dan una evaluación mejor.

Todas devuelven: ajuste (0-100), por_que_encaja (3 frases), alertas y faltantes.
"""
from __future__ import annotations

import re

from .texto import norm

# Vocabulario de habilidades para detectar lo que pide la vacante y te falta.
HABILIDADES_CONOCIDAS = [
    "Python", "SQL", "Excel", "Power BI", "Tableau", "Looker", "Power Automate", "Power Apps",
    "UiPath", "Automation Anywhere", "RPA", "n8n", "Zapier", "JavaScript", "TypeScript", "Node",
    "React", "Java", "C#", ".NET", "Golang", "AWS", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes",
    "Terraform", "Airflow", "dbt", "Spark", "Databricks", "Snowflake", "BigQuery", "pandas", "scikit-learn",
    "PyTorch", "TensorFlow", "machine learning", "deep learning", "NLP", "LLM", "RAG", "LangChain",
    "OpenAI", "Claude", "prompt engineering", "vector database", "API", "ETL", "data warehouse",
    "SAP", "Salesforce", "Dynamics", "SharePoint", "Git", "Linux", "Scrum", "Agile", "estadística",
    "MLOps", "FastAPI", "Flask", "Django", "MongoDB", "PostgreSQL", "Oracle", "Kafka",
]
_TEMAS_OBJETIVO = ["inteligencia artificial", " ia ", " ai ", "machine learning", "aprendizaje automatico",
                   "datos", "data", "automatizacion", "automation", "rpa", "analitica", "analytics",
                   "integracion", "integration", "llm", "genai", "ia generativa", "chatbot", "bot"]
_PALABRAS_VACIAS = {"de", "la", "el", "en", "y", "para", "con", "del", "a", "of", "and", "the", "for", "in",
                    "sr", "jr", "senior", "junior", "ssr", "i", "ii", "iii"}
_LUGARES_RD = ["santo domingo", "republica dominicana", "dominican republic", "distrito nacional",
               "santiago", " rd", "piantini", "naco", "zona franca"]
_REMOTO = re.compile(r"(remoto|remote|hibrid|hybrid|teletrabajo|work from home|desde casa)", re.I)
_PRESENCIAL = re.compile(r"(100\s*% presencial|presencial|on-?site|in-office|en oficina|en sitio)", re.I)
_FINDE = re.compile(r"(fines? de semana|sabados?|domingos|weekends?|turnos? rotativos?|rotating shifts?)", re.I)
_ANOS = re.compile(
    r"(?:(?:minimo|al menos|mas de)\s+)?(\d{1,2})\s*\+?\s*(?:a\s*\d{1,2}\s*)?(?:anos?|years?)"
    r"(?:\s+(?:o mas|or more|\+))?(?:\s+(?:de|of))?\s+(?:experiencia|experience|exp)", re.I)
_SALARIO = re.compile(r"(?:rd\$|dop|\$|salario|sueldo|salary)[^0-9\n]{0,25}(\d{1,3}(?:[.,]\d{3})+|\d{4,7})", re.I)
_GENERICOS = re.compile(r"^(analista|ejecutivo|auxiliar|asistente|coordinador|especialista|encargado|"
                        r"consultor|gestor|representante|oficial)\b\s*$", re.I)


def _contiene(texto_n: str, termino: str) -> bool:
    t = norm(termino)
    if not t:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9#+])", texto_n) is not None


def anos_requeridos(texto: str) -> int:
    return max((int(m) for m in _ANOS.findall(norm(texto))), default=0)


def salario_maximo(texto: str) -> int:
    """El mayor monto mensual en pesos que aparece cerca de 'salario', 'RD$', etc. (0 si no hay)."""
    montos = []
    for m in _SALARIO.finditer(texto or ""):
        valor = int(re.sub(r"[.,]", "", m.group(1)))
        if 10_000 <= valor <= 2_000_000:
            montos.append(valor)
    return max(montos, default=0)


def heuristica(perfil: dict, vacante: dict) -> dict:
    titulo = vacante.get("titulo", "")
    desc = vacante.get("descripcion", "")
    texto = f"{titulo}\n{vacante.get('ubicacion', '')}\n{desc}"
    tn, titn = f" {norm(texto)} ", f" {norm(titulo)} "
    razones, alertas = [], []
    puntos = 20

    # 1. ¿El puesto se parece a lo que buscas?
    mejor_rol, mejor = "", 0.0
    for rol in perfil.get("roles_objetivo", []):
        palabras = [p for p in norm(rol).split() if p not in _PALABRAS_VACIAS]
        if palabras:
            frac = sum(_contiene(titn, p) for p in palabras) / len(palabras)
            if frac > mejor:
                mejor, mejor_rol = frac, rol
    temas = [t.strip() for t in _TEMAS_OBJETIVO if t in titn]
    puntos_rol = round(25 * mejor) + (10 if temas else 0)
    puntos += min(35, puntos_rol)
    if mejor >= 0.5:
        razones.append(f"El puesto coincide con tu objetivo «{mejor_rol}».")
    elif temas:
        razones.append(f"El puesto es del área que buscas ({', '.join(dict.fromkeys(temas))}).")

    # 2. Habilidades
    tuyas = [h for h in perfil.get("habilidades", []) if _contiene(tn, h)]
    if tuyas:
        n = max(3, min(8, len(perfil.get("habilidades", [])) // 2 or 3))
        puntos += round(35 * min(1.0, len(tuyas) / n))
        razones.append(f"Pide habilidades que tienes: {', '.join(tuyas[:5])}.")
    faltan = [h for h in HABILIDADES_CONOCIDAS if _contiene(tn, h)
              and not any(norm(h) == norm(x) or _contiene(f" {norm(x)} ", h) for x in perfil.get("habilidades", []))]

    # 3. Lugar y modalidad
    pref = perfil.get("preferencias", {})
    en_rd = any(l in tn for l in _LUGARES_RD) or not vacante.get("ubicacion")
    remoto = bool(_REMOTO.search(norm(texto)))
    if en_rd or remoto:
        puntos += 10
        if remoto:
            razones.append("Ofrece trabajo remoto o híbrido.")
        elif vacante.get("ubicacion"):
            razones.append(f"Es en {vacante['ubicacion']}, cerca de ti.")
    else:
        alertas.append(f"La ubicación ({vacante.get('ubicacion')}) no parece estar en RD ni ser remota.")
        puntos -= 10
    if pref.get("modalidad") in ("hibrido", "remoto") and _PRESENCIAL.search(norm(texto)) and not remoto:
        alertas.append("Parece ser solo presencial y prefieres algunos días remotos.")
        puntos -= 8
    if _FINDE.search(norm(texto)) and "lunes" in norm(pref.get("dias", "lunes a viernes")):
        alertas.append("Menciona fines de semana o turnos rotativos.")
        puntos -= 5

    # 4. Experiencia y salario
    anos = anos_requeridos(texto)
    tengo = int(perfil.get("anos_experiencia") or 0)
    if anos and anos > tengo:
        alertas.append(f"Pide {anos}+ años de experiencia (tienes {tengo}).")
        puntos -= min(20, 5 * (anos - tengo))
    minimo = int(pref.get("salario_minimo_dop") or 0)
    salario = salario_maximo(texto)
    if minimo and salario and salario < minimo:
        alertas.append(f"El salario indicado (RD${salario:,}) está por debajo de tu mínimo (RD${minimo:,}).")
        puntos -= 15

    # 5. ¿Es vaga?
    if len(desc.strip()) < 250:
        alertas.append("La descripción es muy corta o vaga: revisa el anuncio completo.")
        puntos -= 5
    if _GENERICOS.match(norm(titulo)):
        alertas.append("El título es muy genérico; no queda claro el rol.")
        puntos -= 5

    # 6. Industria de interés (empresa)
    if vacante.get("industria") and any(norm(i) in norm(vacante["industria"]) or norm(vacante["industria"]) in norm(i)
                                        for i in perfil.get("industrias", [])):
        puntos += 5
        razones.append(f"Es de una industria que te interesa ({vacante['industria']}).")

    if not razones:
        razones.append("Pocas coincidencias claras con tu perfil.")
    return {
        "ajuste": max(0, min(95, puntos)),  # la heurística nunca está "segura" al 100 %
        "por_que_encaja": razones[:3],
        "alertas": alertas,
        "faltantes": [f"{h} (lo pide la vacante)" for h in faltan[:6]],
        "puntuado_por": "heurística",
    }
