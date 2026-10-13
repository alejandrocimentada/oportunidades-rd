"""Base de datos local (SQLite): empresas, vacantes, historial de estados y corridas de rastreo.

Para las personas de contacto solo se guardan ROLES (p. ej. "Head of Data"); nunca nombres,
correos, teléfonos ni otros datos personales de individuos.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from pathlib import Path
from typing import Callable, Iterable

from . import config
from .texto import es_portal_bloqueado, idioma, norm, url_canonica

ESTADOS = ["Nuevo", "Me interesa", "Aplicado", "Contacté", "Entrevista", "Oferta", "Rechazado", "Descartado"]
ESTADOS_CERRADOS = {"Rechazado", "Descartado"}
# Estados en los que ya se pueden generar el mensaje y la carta.
ESTADOS_CON_DOCUMENTOS = {"Me interesa", "Aplicado", "Contacté", "Entrevista", "Oferta"}
# Al pasar a estos estados se agenda un seguimiento a los N días (si no hay uno ya).
SEGUIMIENTO_DIAS = {"Aplicado": 7, "Contacté": 5, "Entrevista": 3}

INDUSTRIAS = [
    "banca", "telecomunicaciones", "retail/distribución", "seguros", "zona franca/manufactura",
    "logística", "turismo", "tecnología/consultoría", "gobierno-tech", "salud", "energía", "otra",
]

ESTADOS_RASTREO = ["pendiente", "ok", "sin vacantes", "revisar manualmente", "abrir manualmente",
                   "sin página", "error"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_norm TEXT NOT NULL UNIQUE,
    industria TEXT NOT NULL DEFAULT 'otra',
    sitio_web TEXT NOT NULL DEFAULT '',
    url_empleos TEXT NOT NULL DEFAULT '',
    por_que TEXT NOT NULL DEFAULT '',
    interes INTEGER NOT NULL DEFAULT 50,
    roles_contacto TEXT NOT NULL DEFAULT '[]',
    estado_rastreo TEXT NOT NULL DEFAULT 'pendiente',
    nota_rastreo TEXT NOT NULL DEFAULT '',
    ats TEXT NOT NULL DEFAULT '',
    ultimo_rastreo TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vacantes (
    id INTEGER PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
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
    estado TEXT NOT NULL DEFAULT 'Nuevo',
    estado_fecha TEXT NOT NULL,
    ajuste INTEGER,
    por_que_encaja TEXT NOT NULL DEFAULT '[]',
    alertas TEXT NOT NULL DEFAULT '[]',
    faltantes TEXT NOT NULL DEFAULT '[]',
    puntuado_por TEXT NOT NULL DEFAULT '',
    nota TEXT NOT NULL DEFAULT '',
    seguimiento TEXT NOT NULL DEFAULT '',
    mensaje_path TEXT NOT NULL DEFAULT '',
    carta_path TEXT NOT NULL DEFAULT '',
    activa INTEGER NOT NULL DEFAULT 1,
    primera_vez TEXT NOT NULL,
    ultima_vez TEXT NOT NULL,
    corrida_id INTEGER,
    vista_corrida INTEGER
);
CREATE INDEX IF NOT EXISTS ix_vacantes_url ON vacantes(url_canonica);
CREATE INDEX IF NOT EXISTS ix_vacantes_clave ON vacantes(clave);
CREATE TABLE IF NOT EXISTS historial (
    id INTEGER PRIMARY KEY,
    vacante_id INTEGER NOT NULL REFERENCES vacantes(id) ON DELETE CASCADE,
    de_estado TEXT NOT NULL DEFAULT '',
    a_estado TEXT NOT NULL,
    fecha TEXT NOT NULL,
    nota TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS corridas (
    id INTEGER PRIMARY KEY,
    inicio TEXT NOT NULL,
    fin TEXT NOT NULL DEFAULT '',
    resumen TEXT NOT NULL DEFAULT '{}'
);
"""

JSON_FIELDS = {"roles_contacto", "por_que_encaja", "alertas", "faltantes", "resumen"}

# Un rol de contacto debe parecer un cargo, no un dato personal.
_PARECE_DATO_PERSONAL = re.compile(
    r"@|https?://|www\.|\d{3}[\s.-]?\d{3,4}|\+\d|linkedin\.com/in/", re.I)


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


class Store:
    def __init__(self, path: Path | str | None = None,
                 after_change: Callable[["Store"], None] | None = None):
        self.path = Path(path) if path else config.db_path()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.after_change = after_change

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
    def add_empresa(self, nombre: str, industria: str = "otra", sitio_web: str = "",
                    url_empleos: str = "", por_que: str = "", interes: int = 50,
                    roles: list[str] | None = None) -> dict:
        nombre = " ".join(str(nombre or "").split())
        if not nombre:
            raise DatosError("La empresa necesita un nombre.")
        industria = industria if industria in INDUSTRIAS else "otra"
        interes = int(interes)
        if not 0 <= interes <= 100:
            raise DatosError("El interés debe estar entre 0 y 100.")
        if url_empleos and es_portal_bloqueado(url_empleos):
            raise DatosError(
                "Esa página es de un portal de empleo (LinkedIn, Computrabajo, Indeed…), que no se "
                "rastrea. Deja la página de empleos vacía y usa scripts/pegar.py para esas vacantes.")
        roles = [validar_rol(r) for r in (roles or [])][:5]
        existente = self.conn.execute("SELECT id FROM empresas WHERE nombre_norm = ?", (norm(nombre),)).fetchone()
        if existente:
            return self.update_empresa(existente["id"], industria=None if industria == "otra" else industria,
                                       sitio_web=sitio_web,
                                       url_empleos=url_empleos, por_que=por_que, interes=interes,
                                       roles=roles or None, solo_si_vacio=True)
        estado = "pendiente" if url_empleos else "sin página"
        cur = self.conn.execute(
            "INSERT INTO empresas (nombre, nombre_norm, industria, sitio_web, url_empleos, por_que, interes,"
            " roles_contacto, estado_rastreo, creado) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (nombre, norm(nombre), industria, sitio_web, url_empleos, por_que, interes,
             json.dumps(roles, ensure_ascii=False), estado, ahora()))
        self._changed()
        return self.get_empresa(cur.lastrowid)

    def update_empresa(self, empresa_id: int, solo_si_vacio: bool = False, roles: list[str] | None = None,
                       **campos) -> dict:
        actual = self.get_empresa(empresa_id)
        if not actual:
            raise DatosError(f"No existe la empresa {empresa_id}.")
        permitidos = {"industria", "sitio_web", "url_empleos", "por_que", "interes", "estado_rastreo",
                      "nota_rastreo", "ats", "ultimo_rastreo"}
        cambios: dict = {}
        if "interes" in campos and campos["interes"] is not None:
            campos["interes"] = int(campos["interes"])
            if not 0 <= campos["interes"] <= 100:
                raise DatosError("El interés debe estar entre 0 y 100.")
        for k, v in campos.items():
            if k not in permitidos or v is None:
                continue
            if solo_si_vacio and v == "":  # al volver a agregar, no borra lo que ya había
                continue
            cambios[k] = v
        if "url_empleos" in cambios and cambios["url_empleos"] and es_portal_bloqueado(cambios["url_empleos"]):
            raise DatosError("Esa página es de un portal de empleo que no se rastrea; usa scripts/pegar.py.")
        if "estado_rastreo" in cambios and cambios["estado_rastreo"] not in ESTADOS_RASTREO:
            raise DatosError(f"Estado de rastreo inválido: {cambios['estado_rastreo']}")
        if cambios.get("url_empleos") and cambios["url_empleos"] != actual["url_empleos"]:
            cambios.setdefault("estado_rastreo", "pendiente")
        if roles is not None:
            cambios["roles_contacto"] = json.dumps([validar_rol(r) for r in roles][:5], ensure_ascii=False)
        if cambios:
            sets = ", ".join(f"{k} = ?" for k in cambios)
            self.conn.execute(f"UPDATE empresas SET {sets} WHERE id = ?", (*cambios.values(), empresa_id))
            self._changed()
        return self.get_empresa(empresa_id)

    def get_empresa(self, ref: int | str) -> dict | None:
        if isinstance(ref, int) or str(ref).isdigit():
            row = self.conn.execute("SELECT * FROM empresas WHERE id = ?", (int(ref),)).fetchone()
        else:
            row = self.conn.execute("SELECT * FROM empresas WHERE nombre_norm = ?", (norm(ref),)).fetchone()
        return self._row(row)

    def empresas(self) -> list[dict]:
        return self._rows(self.conn.execute("SELECT * FROM empresas ORDER BY interes DESC, nombre"))

    def remove_empresa(self, empresa_id: int) -> None:
        self.conn.execute("DELETE FROM empresas WHERE id = ?", (empresa_id,))
        self._changed()

    # -- vacantes -------------------------------------------------------------------------
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
            sets = ", ".join(f"{k} = ?" for k in extra)
            self.conn.execute(f"UPDATE vacantes SET {sets} WHERE id = ?", (*extra.values(), existente["id"]))
            if commit:
                self._changed()
            return self.get_vacante(existente["id"]), False
        cur = self.conn.execute(
            "INSERT INTO vacantes (empresa_id, empresa_nombre, titulo, ubicacion, url, url_canonica, clave,"
            " fecha_publicacion, descripcion, fuente, idioma, estado, estado_fecha, primera_vez, ultima_vez,"
            " corrida_id, vista_corrida) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (empresa_id, empresa_nombre, titulo, ubicacion, url, url_canonica(url),
             clave_vacante(empresa_nombre, titulo, ubicacion), fecha_publicacion, descripcion, fuente,
             idioma(f"{titulo}\n{descripcion}"), "Nuevo", momento, momento, momento, corrida_id, corrida_id))
        vid = cur.lastrowid
        self.conn.execute("INSERT INTO historial (vacante_id, de_estado, a_estado, fecha, nota) VALUES (?,?,?,?,?)",
                          (vid, "", "Nuevo", momento, f"Encontrada ({fuente})"))
        if commit:
            self._changed()
        return self.get_vacante(vid), True

    def get_vacante(self, vacante_id: int) -> dict | None:
        return self._row(self.conn.execute("SELECT * FROM vacantes WHERE id = ?", (int(vacante_id),)).fetchone())

    def vacantes(self, estado: str | None = None, min_ajuste: int | None = None,
                 empresa: str | None = None, incluir_inactivas: bool = True) -> list[dict]:
        sql, args = "SELECT * FROM vacantes WHERE 1=1", []
        if estado:
            sql += " AND estado = ?"
            args.append(estado)
        if min_ajuste is not None:
            sql += " AND COALESCE(ajuste, 0) >= ?"
            args.append(min_ajuste)
        if empresa:
            sql += " AND (empresa_nombre LIKE ? OR empresa_id = ?)"
            args += [f"%{empresa}%", empresa if str(empresa).isdigit() else -1]
        if not incluir_inactivas:
            sql += " AND activa = 1"
        sql += " ORDER BY COALESCE(ajuste, -1) DESC, primera_vez DESC"
        return self._rows(self.conn.execute(sql, args))

    def cambiar_estado(self, vacante_id: int, estado: str, nota: str = "") -> dict:
        if estado not in ESTADOS:
            raise DatosError(f"Estado inválido: {estado}. Opciones: {', '.join(ESTADOS)}")
        vac = self.get_vacante(vacante_id)
        if not vac:
            raise DatosError(f"No existe la vacante {vacante_id}.")
        if vac["estado"] == estado:
            return vac
        momento = ahora()
        self.conn.execute("INSERT INTO historial (vacante_id, de_estado, a_estado, fecha, nota) VALUES (?,?,?,?,?)",
                          (vacante_id, vac["estado"], estado, momento, nota))
        seguimiento = vac["seguimiento"]
        if estado in SEGUIMIENTO_DIAS:
            seguimiento = (hoy() + dt.timedelta(days=SEGUIMIENTO_DIAS[estado])).isoformat()
        elif estado in ESTADOS_CERRADOS or estado == "Oferta":
            seguimiento = ""
        self.conn.execute("UPDATE vacantes SET estado = ?, estado_fecha = ?, seguimiento = ? WHERE id = ?",
                          (estado, momento, seguimiento, vacante_id))
        self._changed()
        return self.get_vacante(vacante_id)

    def set_nota(self, vacante_id: int, nota: str) -> dict:
        self._update_vacante(vacante_id, nota=nota)
        return self.get_vacante(vacante_id)

    def set_seguimiento(self, vacante_id: int, fecha: str) -> dict:
        if fecha:
            try:
                fecha = dt.date.fromisoformat(fecha).isoformat()
            except ValueError as exc:
                raise DatosError("La fecha debe tener el formato AAAA-MM-DD.") from exc
        self._update_vacante(vacante_id, seguimiento=fecha or "")
        return self.get_vacante(vacante_id)

    def guardar_puntuacion(self, vacante_id: int, ajuste: int, por_que_encaja: list[str],
                           alertas: list[str], faltantes: list[str], puntuado_por: str) -> dict:
        ajuste = max(0, min(100, int(ajuste)))
        self._update_vacante(vacante_id, ajuste=ajuste,
                             por_que_encaja=json.dumps(list(por_que_encaja)[:3], ensure_ascii=False),
                             alertas=json.dumps(list(alertas), ensure_ascii=False),
                             faltantes=json.dumps(list(faltantes), ensure_ascii=False),
                             puntuado_por=puntuado_por)
        return self.get_vacante(vacante_id)

    def guardar_documento(self, vacante_id: int, tipo: str, path: Path | str) -> dict:
        campo = {"mensaje": "mensaje_path", "carta": "carta_path"}[tipo]
        self._update_vacante(vacante_id, **{campo: str(path)})
        return self.get_vacante(vacante_id)

    def _update_vacante(self, vacante_id: int, **campos) -> None:
        if not self.get_vacante(vacante_id):
            raise DatosError(f"No existe la vacante {vacante_id}.")
        sets = ", ".join(f"{k} = ?" for k in campos)
        self.conn.execute(f"UPDATE vacantes SET {sets} WHERE id = ?", (*campos.values(), vacante_id))
        self._changed()

    def historial(self, vacante_id: int | None = None) -> list[dict]:
        sql = ("SELECT h.*, v.titulo, v.empresa_nombre FROM historial h JOIN vacantes v ON v.id = h.vacante_id")
        if vacante_id is not None:
            return self._rows(self.conn.execute(sql + " WHERE h.vacante_id = ? ORDER BY h.id", (vacante_id,)))
        return self._rows(self.conn.execute(sql + " ORDER BY h.fecha DESC, h.id DESC"))

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
            self.conn.execute(
                f"UPDATE vacantes SET activa = 0 WHERE id IN ({','.join('?' * len(rows))})",
                [r["id"] for r in rows])
            self.conn.commit()
        return rows

    def corridas(self) -> list[dict]:
        return self._rows(self.conn.execute("SELECT * FROM corridas ORDER BY id DESC"))

    def ultima_corrida(self) -> dict | None:
        return self._row(self.conn.execute(
            "SELECT * FROM corridas WHERE fin != '' ORDER BY id DESC LIMIT 1").fetchone())

    def novedades(self, corrida_id: int | None = None) -> dict:
        """Lo nuevo de una corrida (por defecto, la última terminada)."""
        corrida = self._row(self.conn.execute("SELECT * FROM corridas WHERE id = ?", (corrida_id,)).fetchone()) \
            if corrida_id else self.ultima_corrida()
        if not corrida:
            return {"corrida": None, "nuevas": [], "ya_no_aparecen": [], "manuales": []}
        nuevas = self._rows(self.conn.execute(
            "SELECT * FROM vacantes WHERE corrida_id = ? ORDER BY COALESCE(ajuste,-1) DESC", (corrida["id"],)))
        resumen = corrida["resumen"] or {}
        ids_fuera = resumen.get("ya_no_aparecen", [])
        fuera = [self.get_vacante(i) for i in ids_fuera if self.get_vacante(i)]
        return {"corrida": corrida, "nuevas": nuevas, "ya_no_aparecen": fuera,
                "manuales": resumen.get("manuales", [])}

    # -- resumen --------------------------------------------------------------------------
    def resumen(self) -> dict:
        conteo = {e: 0 for e in ESTADOS}
        for row in self.conn.execute("SELECT estado, COUNT(*) n FROM vacantes GROUP BY estado"):
            conteo[row["estado"]] = row["n"]
        inicio_semana = hoy() - dt.timedelta(days=hoy().weekday())
        aplicadas = self.conn.execute(
            "SELECT COUNT(DISTINCT vacante_id) FROM historial WHERE a_estado = 'Aplicado' AND fecha >= ?",
            (inicio_semana.isoformat(),)).fetchone()[0]
        limite = (hoy() + dt.timedelta(days=7)).isoformat()
        seguimientos = self._rows(self.conn.execute(
            "SELECT * FROM vacantes WHERE seguimiento != '' AND seguimiento <= ? AND estado NOT IN"
            " ('Rechazado','Descartado','Oferta') ORDER BY seguimiento", (limite,)))
        for s in seguimientos:
            s["vencido"] = s["seguimiento"] < hoy().isoformat()
        return {
            "por_estado": conteo,
            "total_vacantes": sum(conteo.values()),
            "total_empresas": self.conn.execute("SELECT COUNT(*) FROM empresas").fetchone()[0],
            "aplicadas_semana": aplicadas,
            "seguimientos": seguimientos,
            "sin_puntuar": self.conn.execute("SELECT COUNT(*) FROM vacantes WHERE ajuste IS NULL").fetchone()[0],
            "ultima_corrida": self.ultima_corrida(),
        }


def columnas(store: Store, tabla: str) -> list[str]:
    return [r["name"] for r in store.conn.execute(f"PRAGMA table_info({tabla})")]
