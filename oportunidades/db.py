"""Base de datos local (SQLite): empresas donde podrías trabajar, su seguimiento, y las vacantes abiertas
que el rastreador encuentra (como comprobación secundaria).

El centro es la EMPRESA: presencia verificada en RD (con fuentes), equipos y roles probables para tu
perfil, evidencia, por qué encaja, señales de alerta y cómo postular. No hay puntuación numérica.

Para las personas de contacto solo se guardan ROLES (p. ej. "Head of Data"); nunca nombres,
correos, teléfonos ni otros datos personales de individuos.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Iterable

from . import config
from .texto import es_portal_bloqueado, idioma, norm, url_canonica

ESTADOS = ["Descubierta", "Me interesa", "Investigando", "Contacté", "Aplicado", "Entrevista", "Oferta", "Descartada"]
ESTADOS_CERRADOS = {"Descartada"}
# Estados en los que ya se pueden preparar el mensaje y la carta (solo empresas que elegiste).
ESTADOS_CON_DOCUMENTOS = {"Me interesa", "Investigando", "Contacté", "Aplicado", "Entrevista", "Oferta"}
# Al pasar a estos estados se agenda un seguimiento a los N días.
SEGUIMIENTO_DIAS = {"Contacté": 5, "Aplicado": 7, "Entrevista": 3}

TIPOS_EMPRESA = ["multinacional", "grupo local", "empresa local en crecimiento", "tecnología/startup", "otra"]
INDUSTRIAS = [
    "banca", "telecomunicaciones", "retail/distribución", "seguros", "zona franca/manufactura",
    "logística", "turismo", "tecnología/consultoría", "gobierno-tech", "salud", "energía", "otra",
]
ESTADOS_RASTREO = ["pendiente", "ok", "sin vacantes", "revisar manualmente", "abrir manualmente",
                   "sin página", "error"]

VERSION_ESQUEMA = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_norm TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL DEFAULT 'otra',
    industria TEXT NOT NULL DEFAULT 'otra',
    sitio_web TEXT NOT NULL DEFAULT '',
    presencia_rd TEXT NOT NULL DEFAULT '',
    fuentes_presencia TEXT NOT NULL DEFAULT '[]',
    equipos TEXT NOT NULL DEFAULT '[]',
    roles TEXT NOT NULL DEFAULT '[]',
    evidencia TEXT NOT NULL DEFAULT '[]',
    razones TEXT NOT NULL DEFAULT '[]',
    alertas TEXT NOT NULL DEFAULT '[]',
    url_empleos TEXT NOT NULL DEFAULT '',
    portal_rd TEXT NOT NULL DEFAULT '',
    talento TEXT NOT NULL DEFAULT '',
    linkedin_empresa TEXT NOT NULL DEFAULT '',
    roles_contacto TEXT NOT NULL DEFAULT '[]',
    estado TEXT NOT NULL DEFAULT 'Descubierta',
    estado_fecha TEXT NOT NULL,
    nota TEXT NOT NULL DEFAULT '',
    seguimiento TEXT NOT NULL DEFAULT '',
    mensaje_path TEXT NOT NULL DEFAULT '',
    carta_path TEXT NOT NULL DEFAULT '',
    estado_rastreo TEXT NOT NULL DEFAULT 'pendiente',
    nota_rastreo TEXT NOT NULL DEFAULT '',
    ats TEXT NOT NULL DEFAULT '',
    ultimo_rastreo TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historial (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    de_estado TEXT NOT NULL DEFAULT '',
    a_estado TEXT NOT NULL,
    fecha TEXT NOT NULL,
    nota TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vacantes (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE,
    empresa_nombre TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL,
    ubicacion TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    url_canonica TEXT NOT NULL DEFAULT '',
    clave TEXT NOT NULL,
    fecha_publicacion TEXT NOT NULL DEFAULT '',
    descripcion TEXT NOT NULL DEFAULT '',
    fuente TEXT NOT NULL DEFAULT 'rastreo',
    idioma TEXT NOT NULL DEFAULT 'es',
    activa INTEGER NOT NULL DEFAULT 1,
    primera_vez TEXT NOT NULL,
    ultima_vez TEXT NOT NULL,
    corrida_id INTEGER,
    vista_corrida INTEGER
);
CREATE INDEX IF NOT EXISTS ix_vacantes_url ON vacantes(url_canonica);
CREATE INDEX IF NOT EXISTS ix_vacantes_clave ON vacantes(clave);
CREATE TABLE IF NOT EXISTS corridas (
    id INTEGER PRIMARY KEY,
    inicio TEXT NOT NULL,
    fin TEXT NOT NULL DEFAULT '',
    resumen TEXT NOT NULL DEFAULT '{}'
);
"""

JSON_FIELDS = {"fuentes_presencia", "equipos", "roles", "evidencia", "razones", "alertas", "roles_contacto", "resumen"}

# Un rol de contacto debe parecer un cargo, no un dato personal.
_PARECE_DATO_PERSONAL = re.compile(r"@|https?://|www\.|\d{3}[\s.-]?\d{3,4}|\+\d|linkedin\.com/in/", re.I)
_PERFIL_PERSONAL = re.compile(r"linkedin\.com/(in|pub)/", re.I)


class DatosError(ValueError):
    """Dato inválido."""


def ahora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def hoy() -> dt.date:
    return dt.date.today()


def clave_vacante(empresa: str, titulo: str, ubicacion: str = "") -> str:
    return f"{norm(empresa)}|{norm(titulo)}|{norm(ubicacion)}"


def validar_rol(rol: str) -> str:
    rol = " ".join(str(rol or "").split())
    if not rol:
        raise DatosError("El rol está vacío.")
    if len(rol) > 80 or _PARECE_DATO_PERSONAL.search(rol):
        raise DatosError(
            f"'{rol}' no parece un cargo. Guarda solo roles (p. ej. 'Gerente de Innovación'), "
            "nunca nombres, correos, teléfonos ni perfiles de personas.")
    return rol


def _texto(valor, maximo: int = 600) -> str:
    return " ".join(str(valor or "").split())[:maximo]


def _url(valor, campo: str, obligatoria: bool = False) -> str:
    url = str(valor or "").strip()
    if not url:
        if obligatoria:
            raise DatosError(f"Falta el enlace en «{campo}».")
        return ""
    if not re.match(r"^https?://[^\s/]+\.[^\s]+$", url, re.I):
        raise DatosError(f"«{url}» no es un enlace válido ({campo}). Usa una URL completa con https://")
    if _PERFIL_PERSONAL.search(url):
        raise DatosError(f"«{url}» es el perfil de una persona ({campo}). No se guardan datos de individuos.")
    return url


def _lista_textos(valor, maximo: int = 8) -> list[str]:
    if isinstance(valor, str):
        valor = [x for x in re.split(r"[;\n]", valor)]
    return [t for t in (_texto(x, 300) for x in (valor or [])) if t][:maximo]


def _lista_enlaces(valor, campo: str, clave_texto: str, url_obligatoria: bool, maximo: int = 10) -> list[dict]:
    """Normaliza [{texto|titulo, url}] o ["https://..."] → [{clave_texto: ..., "url": ...}]."""
    out = []
    for item in valor or []:
        if isinstance(item, str):
            item = {"url": item} if item.strip().lower().startswith("http") else {clave_texto: item}
        if not isinstance(item, dict):
            raise DatosError(f"Formato inválido en «{campo}»: {item!r}")
        texto = _texto(item.get(clave_texto) or item.get("texto") or item.get("titulo"), 300)
        url = _url(item.get("url"), campo, obligatoria=url_obligatoria)
        if texto or url:
            out.append({clave_texto: texto, "url": url})
    return out[:maximo]


def _lista_roles(valor) -> list[dict]:
    out = []
    for item in valor or []:
        if isinstance(item, str):
            rol, _, razon = item.partition(":")
            item = {"rol": rol, "razon": razon}
        rol = _texto(item.get("rol"), 120)
        if rol:
            out.append({"rol": rol, "razon": _texto(item.get("razon"), 400)})
    return out[:6]


def validar_empresa(data: dict, nueva: bool) -> dict:
    """Limpia y valida los datos de una empresa. Una empresa nueva necesita al menos una fuente que
    verifique su presencia en la República Dominicana."""
    out: dict = {}
    if "nombre" in data:
        out["nombre"] = _texto(data["nombre"], 120)
    if nueva and not out.get("nombre"):
        raise DatosError("La empresa necesita un nombre.")
    if "tipo" in data:
        out["tipo"] = data["tipo"] if data["tipo"] in TIPOS_EMPRESA else "otra"
    if "industria" in data:
        out["industria"] = data["industria"] if data["industria"] in INDUSTRIAS else "otra"
    for campo in ("presencia_rd",):
        if campo in data:
            out[campo] = _texto(data[campo])
    for campo in ("sitio_web", "url_empleos", "portal_rd", "talento"):
        if campo in data:
            out[campo] = _url(data[campo], campo)
    if out.get("url_empleos") and es_portal_bloqueado(out["url_empleos"]):
        raise DatosError(
            "La página de empleos que se rastrea no puede ser un portal (LinkedIn, Computrabajo, Indeed…). "
            "Ponla en «portal_rd» (solo es un enlace para ti) y deja «url_empleos» vacía.")
    if "linkedin_empresa" in data:
        out["linkedin_empresa"] = _url(data["linkedin_empresa"], "linkedin_empresa")
        if out["linkedin_empresa"] and not re.search(r"linkedin\.com/(company|school|showcase)/",
                                                     out["linkedin_empresa"], re.I):
            raise DatosError("«linkedin_empresa» debe ser la página de la empresa (linkedin.com/company/…).")
    if "fuentes_presencia" in data:
        out["fuentes_presencia"] = _lista_enlaces(data["fuentes_presencia"], "fuentes_presencia", "titulo", True)
    if nueva and not out.get("fuentes_presencia"):
        raise DatosError(
            f"«{out.get('nombre', '?')}»: sin al menos una fuente (enlace) que verifique su presencia en la "
            "República Dominicana, no se agrega.")
    if "evidencia" in data:
        out["evidencia"] = _lista_enlaces(data["evidencia"], "evidencia", "texto", False)
    if "equipos" in data:
        out["equipos"] = _lista_textos(data["equipos"])
    if "roles" in data:
        out["roles"] = _lista_roles(data["roles"])
    if "razones" in data:
        out["razones"] = _lista_textos(data["razones"], 3)
    if "alertas" in data:
        out["alertas"] = _lista_textos(data["alertas"])
    if "roles_contacto" in data:
        out["roles_contacto"] = [validar_rol(r) for r in _lista_textos(data["roles_contacto"], 5)]
    return out


class Store:
    def __init__(self, path: Path | str | None = None,
                 after_change: Callable[["Store"], None] | None = None):
        self.path = Path(path) if path else config.db_path()
        self.conn = self._conectar()
        if _es_esquema_anterior(self.conn):
            self.conn.close()
            respaldo = self.path.with_name(f"{self.path.stem}.v1-{dt.datetime.now():%Y%m%d-%H%M%S}.db")
            self.path.rename(respaldo)
            print(f"Aviso: la base de datos era de la versión anterior (vacantes con puntuación). "
                  f"Se guardó en {respaldo.name} y se empezó una nueva.", file=sys.stderr)
            self.conn = self._conectar()
        self.conn.executescript(SCHEMA)
        self.conn.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")
        self.after_change = after_change

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # -- utilidades -----------------------------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _changed(self) -> None:
        self.conn.commit()
        if self.after_change:
            self.after_change(self)

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        out = dict(row)
        for k in JSON_FIELDS & out.keys():
            out[k] = json.loads(out[k] or "[]")
        return out

    def _rows(self, rows: Iterable[sqlite3.Row]) -> list[dict]:
        return [self._row(r) for r in rows]

    # -- empresas -------------------------------------------------------------------------
    _SELECT_EMPRESA = ("SELECT e.*, (SELECT COUNT(*) FROM vacantes v WHERE v.empresa_id = e.id AND v.activa = 1)"
                       " AS vacantes_activas FROM empresas e")

    def guardar_empresa(self, data: dict) -> tuple[dict, bool]:
        """Agrega una empresa o, si ya existe (mismo nombre), actualiza los campos que traiga.
        Devuelve (empresa, es_nueva)."""
        nombre = _texto(data.get("nombre"), 120)
        existente = self.conn.execute("SELECT id FROM empresas WHERE nombre_norm = ?", (norm(nombre),)).fetchone() \
            if nombre else None
        if existente:
            return self.update_empresa(existente["id"], **{k: v for k, v in data.items() if k != "nombre"}), False
        limpio = validar_empresa(data, nueva=True)
        momento = ahora()
        limpio.setdefault("estado_rastreo", "pendiente" if limpio.get("url_empleos") else "sin página")
        cols = dict(limpio, nombre_norm=norm(limpio["nombre"]), estado="Descubierta", estado_fecha=momento,
                    creado=momento)
        cols = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS else v) for k, v in cols.items()}
        cur = self.conn.execute(f"INSERT INTO empresas ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                                tuple(cols.values()))
        fuente = limpio["fuentes_presencia"][0]["url"]
        self.conn.execute("INSERT INTO historial (empresa_id, de_estado, a_estado, fecha, nota) VALUES (?,?,?,?,?)",
                          (cur.lastrowid, "", "Descubierta", momento, f"Presencia en RD verificada: {fuente}"))
        self._changed()
        return self.get_empresa(cur.lastrowid), True

    def update_empresa(self, empresa_id: int, **campos) -> dict:
        actual = self.get_empresa(empresa_id)
        if not actual:
            raise DatosError(f"No existe la empresa {empresa_id}.")
        internos = {k: campos.pop(k) for k in ("estado_rastreo", "nota_rastreo", "ats", "ultimo_rastreo")
                    if k in campos}
        cambios = validar_empresa({k: v for k, v in campos.items() if v is not None}, nueva=False)
        cambios.pop("nombre", None)
        if "fuentes_presencia" in cambios and not cambios["fuentes_presencia"]:
            raise DatosError("La empresa debe conservar al menos una fuente de su presencia en RD.")
        if "estado_rastreo" in internos and internos["estado_rastreo"] not in ESTADOS_RASTREO:
            raise DatosError(f"Estado de rastreo inválido: {internos['estado_rastreo']}")
        if "url_empleos" in cambios and cambios["url_empleos"] != actual["url_empleos"]:
            internos.setdefault("estado_rastreo", "pendiente" if cambios["url_empleos"] else "sin página")
        cambios.update(internos)
        if cambios:
            vals = [json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS else v for k, v in cambios.items()]
            self.conn.execute(f"UPDATE empresas SET {', '.join(f'{k} = ?' for k in cambios)} WHERE id = ?",
                              (*vals, empresa_id))
            self._changed()
        return self.get_empresa(empresa_id)

    def get_empresa(self, ref: int | str) -> dict | None:
        if isinstance(ref, int) or str(ref).isdigit():
            row = self.conn.execute(self._SELECT_EMPRESA + " WHERE e.id = ?", (int(ref),)).fetchone()
        else:
            row = self.conn.execute(self._SELECT_EMPRESA + " WHERE e.nombre_norm = ?", (norm(ref),)).fetchone()
        return _con_vacantes(self._row(row))

    def empresas(self, estado: str | None = None) -> list[dict]:
        sql, args = self._SELECT_EMPRESA, []
        if estado:
            sql, args = sql + " WHERE e.estado = ?", [estado]
        orden = " ORDER BY CASE e.estado " + " ".join(f"WHEN '{s}' THEN {i}" for i, s in enumerate(ESTADOS)) + \
            " END, e.nombre"
        return [_con_vacantes(e) for e in self._rows(self.conn.execute(sql + orden, args))]

    def remove_empresa(self, empresa_id: int) -> None:
        self.conn.execute("DELETE FROM empresas WHERE id = ?", (empresa_id,))
        self._changed()

    def cambiar_estado(self, empresa_id: int, estado: str, nota: str = "") -> dict:
        if estado not in ESTADOS:
            raise DatosError(f"Estado inválido: {estado}. Opciones: {', '.join(ESTADOS)}")
        emp = self.get_empresa(empresa_id)
        if not emp:
            raise DatosError(f"No existe la empresa {empresa_id}.")
        if emp["estado"] == estado:
            return emp
        momento = ahora()
        self.conn.execute("INSERT INTO historial (empresa_id, de_estado, a_estado, fecha, nota) VALUES (?,?,?,?,?)",
                          (empresa_id, emp["estado"], estado, momento, nota))
        seguimiento = emp["seguimiento"]
        if estado in SEGUIMIENTO_DIAS:
            seguimiento = (hoy() + dt.timedelta(days=SEGUIMIENTO_DIAS[estado])).isoformat()
        elif estado in ESTADOS_CERRADOS or estado == "Oferta":
            seguimiento = ""
        self.conn.execute("UPDATE empresas SET estado = ?, estado_fecha = ?, seguimiento = ? WHERE id = ?",
                          (estado, momento, seguimiento, empresa_id))
        self._changed()
        return self.get_empresa(empresa_id)

    def set_nota(self, empresa_id: int, nota: str) -> dict:
        return self._set(empresa_id, nota=str(nota or ""))

    def set_seguimiento(self, empresa_id: int, fecha: str) -> dict:
        if fecha:
            try:
                fecha = dt.date.fromisoformat(fecha).isoformat()
            except ValueError as exc:
                raise DatosError("La fecha debe tener el formato AAAA-MM-DD.") from exc
        return self._set(empresa_id, seguimiento=fecha or "")

    def guardar_documento(self, empresa_id: int, tipo: str, path: Path | str) -> dict:
        return self._set(empresa_id, **{{"mensaje": "mensaje_path", "carta": "carta_path"}[tipo]: str(path)})

    def _set(self, empresa_id: int, **campos) -> dict:
        if not self.get_empresa(empresa_id):
            raise DatosError(f"No existe la empresa {empresa_id}.")
        self.conn.execute(f"UPDATE empresas SET {', '.join(f'{k} = ?' for k in campos)} WHERE id = ?",
                          (*campos.values(), empresa_id))
        self._changed()
        return self.get_empresa(empresa_id)

    def historial(self, empresa_id: int | None = None) -> list[dict]:
        sql = "SELECT h.*, e.nombre AS empresa_nombre FROM historial h JOIN empresas e ON e.id = h.empresa_id"
        if empresa_id is not None:
            return self._rows(self.conn.execute(sql + " WHERE h.empresa_id = ? ORDER BY h.id", (empresa_id,)))
        return self._rows(self.conn.execute(sql + " ORDER BY h.fecha DESC, h.id DESC"))

    # -- vacantes (comprobación secundaria: ¿hay vacantes abiertas?) ----------------------
    def buscar_duplicado(self, empresa: str, titulo: str, ubicacion: str = "", url: str = "") -> dict | None:
        canon = url_canonica(url)
        if canon:
            row = self.conn.execute("SELECT * FROM vacantes WHERE url_canonica = ?", (canon,)).fetchone()
            if row:
                return self._row(row)
        row = self.conn.execute("SELECT * FROM vacantes WHERE clave = ?",
                                (clave_vacante(empresa, titulo, ubicacion),)).fetchone()
        return self._row(row)

    def upsert_vacante(self, titulo: str, empresa_id: int | None = None, empresa_nombre: str = "",
                       ubicacion: str = "", url: str = "", fecha_publicacion: str = "",
                       descripcion: str = "", fuente: str = "rastreo", corrida_id: int | None = None,
                       commit: bool = True) -> tuple[dict, bool]:
        """Guarda una vacante. Devuelve (vacante, es_nueva). Si ya existe, actualiza 'ultima_vez'."""
        titulo = " ".join(str(titulo or "").split())
        if not titulo:
            raise DatosError("La vacante necesita un título.")
        if empresa_id and not empresa_nombre:
            emp = self.get_empresa(empresa_id)
            empresa_nombre = emp["nombre"] if emp else ""
        existente = self.buscar_duplicado(empresa_nombre, titulo, ubicacion, url)
        momento = ahora()
        if existente:
            extra = {}
            if descripcion and len(descripcion) > len(existente["descripcion"]):
                extra["descripcion"] = descripcion
                extra["idioma"] = idioma(f"{titulo}\n{descripcion}")
            if fecha_publicacion and not existente["fecha_publicacion"]:
                extra["fecha_publicacion"] = fecha_publicacion
            if url and not existente["url"]:
                extra["url"], extra["url_canonica"] = url, url_canonica(url)
            extra["ultima_vez"], extra["activa"] = momento, 1
            if corrida_id:
                extra["vista_corrida"] = corrida_id
            self.conn.execute(f"UPDATE vacantes SET {', '.join(f'{k} = ?' for k in extra)} WHERE id = ?",
                              (*extra.values(), existente["id"]))
            if commit:
                self._changed()
            return self.get_vacante(existente["id"]), False
        cur = self.conn.execute(
            "INSERT INTO vacantes (empresa_id, empresa_nombre, titulo, ubicacion, url, url_canonica, clave,"
            " fecha_publicacion, descripcion, fuente, idioma, primera_vez, ultima_vez, corrida_id, vista_corrida)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (empresa_id, empresa_nombre, titulo, ubicacion, url, url_canonica(url),
             clave_vacante(empresa_nombre, titulo, ubicacion), fecha_publicacion, descripcion, fuente,
             idioma(f"{titulo}\n{descripcion}"), momento, momento, corrida_id, corrida_id))
        if commit:
            self._changed()
        return self.get_vacante(cur.lastrowid), True

    def get_vacante(self, vacante_id: int) -> dict | None:
        return self._row(self.conn.execute("SELECT * FROM vacantes WHERE id = ?", (int(vacante_id),)).fetchone())

    def vacantes(self, empresa: str | int | None = None, incluir_inactivas: bool = True) -> list[dict]:
        sql, args = "SELECT * FROM vacantes WHERE 1=1", []
        if empresa:
            sql += " AND (empresa_nombre LIKE ? OR empresa_id = ?)"
            args += [f"%{empresa}%", int(empresa) if str(empresa).isdigit() else -1]
        if not incluir_inactivas:
            sql += " AND activa = 1"
        return self._rows(self.conn.execute(sql + " ORDER BY activa DESC, primera_vez DESC, id DESC", args))

    # -- corridas y novedades -------------------------------------------------------------
    def iniciar_corrida(self) -> int:
        cur = self.conn.execute("INSERT INTO corridas (inicio) VALUES (?)", (ahora(),))
        self.conn.commit()
        return cur.lastrowid

    def terminar_corrida(self, corrida_id: int, resumen: dict) -> None:
        self.conn.execute("UPDATE corridas SET fin = ?, resumen = ? WHERE id = ?",
                          (ahora(), json.dumps(resumen, ensure_ascii=False), corrida_id))
        self._changed()

    def marcar_no_vistas(self, empresa_id: int, corrida_id: int) -> list[dict]:
        """Vacantes de una empresa rastreada que no aparecieron en esta corrida → activa = 0."""
        rows = self._rows(self.conn.execute(
            "SELECT * FROM vacantes WHERE empresa_id = ? AND fuente != 'pegado' AND activa = 1"
            " AND COALESCE(vista_corrida, 0) != ?", (empresa_id, corrida_id)))
        if rows:
            self.conn.execute(f"UPDATE vacantes SET activa = 0 WHERE id IN ({','.join('?' * len(rows))})",
                              [r["id"] for r in rows])
            self.conn.commit()
        return rows

    def ultima_corrida(self) -> dict | None:
        return self._row(self.conn.execute(
            "SELECT * FROM corridas WHERE fin != '' ORDER BY id DESC LIMIT 1").fetchone())

    def novedades(self, corrida_id: int | None = None) -> dict:
        """Lo nuevo de una corrida de rastreo (por defecto, la última terminada)."""
        corrida = self._row(self.conn.execute("SELECT * FROM corridas WHERE id = ?", (corrida_id,)).fetchone()) \
            if corrida_id else self.ultima_corrida()
        if not corrida:
            return {"corrida": None, "nuevas": [], "ya_no_aparecen": [], "manuales": []}
        nuevas = self._rows(self.conn.execute(
            "SELECT * FROM vacantes WHERE corrida_id = ? ORDER BY empresa_nombre, titulo", (corrida["id"],)))
        resumen = corrida["resumen"] or {}
        fuera = [v for v in (self.get_vacante(i) for i in resumen.get("ya_no_aparecen", [])) if v]
        return {"corrida": corrida, "nuevas": nuevas, "ya_no_aparecen": fuera, "manuales": resumen.get("manuales", [])}

    # -- resumen --------------------------------------------------------------------------
    def resumen(self) -> dict:
        conteo = {e: 0 for e in ESTADOS}
        for row in self.conn.execute("SELECT estado, COUNT(*) n FROM empresas GROUP BY estado"):
            conteo[row["estado"]] = row["n"]
        inicio_semana = (hoy() - dt.timedelta(days=hoy().weekday())).isoformat()
        contactadas = self.conn.execute(
            "SELECT COUNT(DISTINCT empresa_id) FROM historial WHERE a_estado IN ('Contacté', 'Aplicado')"
            " AND fecha >= ?", (inicio_semana,)).fetchone()[0]
        limite = (hoy() + dt.timedelta(days=7)).isoformat()
        seguimientos = self._rows(self.conn.execute(
            "SELECT id, nombre, estado, seguimiento FROM empresas WHERE seguimiento != '' AND seguimiento <= ?"
            " AND estado NOT IN ('Descartada', 'Oferta') ORDER BY seguimiento", (limite,)))
        for s in seguimientos:
            s["vencido"] = s["seguimiento"] < hoy().isoformat()
        recientes = self._rows(self.conn.execute(
            "SELECT id, nombre, tipo, industria, presencia_rd, estado, creado FROM empresas"
            " ORDER BY creado DESC, id DESC LIMIT 8"))
        con_vacantes = self.conn.execute(
            "SELECT COUNT(DISTINCT empresa_id) FROM vacantes WHERE activa = 1 AND empresa_id IS NOT NULL").fetchone()[0]
        return {
            "por_estado": conteo,
            "total_empresas": sum(conteo.values()),
            "contactadas_semana": contactadas,
            "seguimientos": seguimientos,
            "recientes": recientes,
            "empresas_con_vacantes": con_vacantes,
            "vacantes_activas": self.conn.execute("SELECT COUNT(*) FROM vacantes WHERE activa = 1").fetchone()[0],
            "ultima_corrida": self.ultima_corrida(),
        }


def vacantes_texto(empresa: dict) -> str:
    """«hay vacantes» / «no hay» / el estado del rastreo cuando no se pudo saber."""
    n, estado = empresa.get("vacantes_activas", 0), empresa.get("estado_rastreo", "")
    if n:
        return "hay vacantes"
    if estado in ("ok", "sin vacantes"):
        return "no hay"
    return {"pendiente": "sin revisar", "sin página": "sin página de empleos"}.get(estado, estado)


def _con_vacantes(e: dict | None) -> dict | None:
    if e is not None:
        e["vacantes"] = vacantes_texto(e)
    return e


def _es_esquema_anterior(conn: sqlite3.Connection) -> bool:
    """La versión 1 guardaba vacantes con puntuación (columna 'ajuste') y empresas con 'interes'."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(empresas)")]
    return bool(cols) and "interes" in cols


def columnas(store: Store, tabla: str) -> list[str]:
    return [r["name"] for r in store.conn.execute(f"PRAGMA table_info({tabla})")]
