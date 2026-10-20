**Español** · [English](README.en.md)

![Oportunidades RD](docs/banner.png)

<p align="center"><strong>Un agente de IA que te ayuda a encontrar dónde podrías trabajar en la República Dominicana según tu perfil, aunque esas empresas no tengan vacantes publicadas: qué equipos encajan contigo, qué roles probables hay para ti, cómo postular y a quién contactar. Todo en tu computadora, con un tablero y un Excel.</strong></p>

## ¿Qué es esto?

**Oportunidades RD** es un "skill" (un paquete de instrucciones y herramientas) que se instala en
tu asistente de IA, como Claude Code. Le dices *"busca empresas en RD para mi perfil"* y:

1. **Te conoce**: la primera vez eliges qué áreas te interesan y cuentas qué estudiaste y dónde
   trabajas; te sugiere habilidades y roles (cada uno con su porqué) y tú eliges. Luego idiomas, cómo
   quieres trabajar y salario. Tu perfil se guarda en tu computadora.
2. **Descubre empresas con presencia verificada en RD**: multinacionales con operaciones aquí
   (oficinas, hubs regionales, centros de servicios compartidos, plantas de zona franca), grupos
   locales grandes, empresas locales en crecimiento y empresas de tecnología o startups que operan
   o contratan en RD. Cada una lleva **al menos una fuente** (sitio de la empresa, noticia,
   directorio de zonas francas, registro oficial). Si no se puede verificar, no se agrega.
3. **Explica por qué encaja contigo**, sin puntuaciones: qué **equipos** de esa empresa encajan con
   tu perfil, qué **roles probables** hay para alguien como tú (con la razón), **evidencia** de que
   esos equipos existen en RD (vacantes pasadas o actuales, páginas, noticias), las **3 razones
   principales** y las **señales de alerta** (solo roles presenciales de planta, pide algo que no
   tienes, sin modalidad híbrida…).
4. **Te dice cómo postular**: portal de empleos (filtrado a RD si se puede), banco de talento o
   postulación general, página de LinkedIn de la empresa y 2–3 **cargos** a contactar, cada uno con
   un enlace de búsqueda de LinkedIn que abres tú.
5. **Revisa si hay vacantes abiertas**, como comprobación secundaria: visita con educación sus
   páginas de empleo y te dice "hay vacantes" o "no hay".
6. **Tú eliges.** Solo para las empresas que marcas "Me interesa", prepara un **mensaje corto** y una
   **carta de postulación general**, adaptados al equipo y al rol probable, con enlaces a tu trabajo.
7. **Llevas el control** en un tablero y un Excel: Descubierta → Me interesa → Investigando →
   Contacté → Aplicado → Entrevista → Oferta / Descartada, con fechas y notas.

## ¿Para quién es?

Para cualquier persona que busca empleo en la República Dominicana, en cualquier área: la búsqueda
se hace a partir de **tu** perfil (intereses, experiencia, habilidades, roles y preferencias).
No necesitas saber programar: el asistente de IA hace la parte técnica.

> [!IMPORTANT]
> **Todo queda en tu computadora.** Tu perfil y tus empresas se guardan en archivos locales.
> No hay cuenta ni servidor de Oportunidades RD.
> **Nada se envía solo.** El mensaje y la carta se guardan como archivos; tú los revisas y los envías.
> **No entra a LinkedIn, Computrabajo ni Indeed.** Si ves una vacante ahí, la copias y la pegas tú.
> **No guarda datos de personas.** Para "a quién contactar" solo sugiere **cargos** y te da un
> enlace de búsqueda de LinkedIn que abres tú, con tu cuenta.
> **Verifica antes de escribir.** La investigación la hace tu agente con búsquedas web: revisa las
> fuentes de cada empresa.

## Cómo usarlo (la forma más fácil)

1. **Pídele a tu asistente de IA que lo instale.** Si usas Claude Code u otro agente de IA
   (un asistente que puede trabajar con archivos en tu computadora), copia y pega este mensaje:

   ```text
   Instala el skill oportunidades-rd desde https://github.com/alejandrocimentada/oportunidades-rd y ábreme el panel.
   ```

   <details>
   <summary><b>¿No tienes un agente de IA? Así empiezas (5 minutos)</b></summary>

   1. **Qué es un agente de IA:** un asistente, como Claude Code, que puede trabajar con archivos
      en tu computadora: leerlos, ejecutar programas y explicarte los resultados.
   2. **Abre la terminal** (la ventana donde se escriben comandos):
      - Windows: presiona la tecla Windows, escribe "PowerShell" y ábrelo.
      - Mac: presiona Cmd + Espacio, escribe "Terminal" y ábrela.
   3. **Instala Claude Code** siguiendo la
      [guía oficial de inicio rápido](https://code.claude.com/docs/es/quickstart) (pasos 1 y 2).
      Necesitarás una cuenta de Claude; la guía explica qué planes incluyen Claude Code.
   4. **Escribe `claude`** y presiona Enter para abrir el agente. La primera vez te pedirá
      iniciar sesión con tu cuenta de Claude. Luego pega el mensaje del paso 1.

   </details>

2. **Llena tu perfil**: en la conversación, o en la pestaña **Mi perfil** del tablero (ocho pasos
   cortos: intereses, experiencia, habilidades y roles sugeridos, idiomas, dónde, salario y nombre). Si no sabes algo, di "no sé" y sigue. Se guarda en `~/.config/oportunidades-rd/profile.yaml`,
   fuera de la carpeta del proyecto.

3. **Pídele lo que necesites**, con tus palabras:

   > Busca empresas en RD para mi perfil.
   > ¿Qué equipos de Empresa X encajan conmigo? ¿Qué me falta?
   > Revisa si tienen vacantes abiertas.
   > Marca Empresa X como "Me interesa" y prepárame el mensaje y la carta para el rol de BI Analyst.
   > Pasa Empresa X a "Contacté": le escribí a Talent Acquisition.
   > Abre el tablero.

## El tablero

Pídele al asistente *"abre el tablero"*, o escribe `python app.py` en la carpeta del proyecto.
Se abre en tu navegador en <http://localhost:8765> (solo tu computadora puede verlo).

- **Mi perfil**: ocho pasos. Las habilidades y los roles se sugieren a partir de tus intereses y tu
  experiencia, sin IA (con un mapa local); si tu agente está trabajando, puede afinarlas para ti.
- **Resumen**: cuántas empresas hay en cada estado, las últimas descubiertas, contactos de esta
  semana, próximos seguimientos y vacantes abiertas del último rastreo.
- **Tablero**: una columna por estado. **Arrastra una empresa** para cambiarla de estado.
- **Empresas**: filtros por estado, tipo, industria y "solo con vacantes abiertas".
- **Vacantes**: las vacantes publicadas que encontró el rastreador (comprobación secundaria).
- **Detalle** de cada empresa: presencia en RD con sus fuentes, equipos, roles probables, evidencia,
  por qué encaja, señales de alerta, cómo postular, a quién contactar, vacantes abiertas, el mensaje
  y la carta con botón **Copiar**, tus notas y el historial con fechas.

*(Las capturas de `docs/` son de una versión anterior y usan datos inventados.)*

## El Excel

`data/oportunidades.xlsx` se actualiza solo después de cada cambio. Tiene cuatro hojas, con filtros,
encabezados fijos y colores por estado: **Resumen**, **Empresas** (todo el análisis de cada una),
**Vacantes** y **Seguimiento** (cada cambio de estado con su fecha). También puedes bajarlo desde el
botón *Descargar Excel* del tablero. Si lo tienes abierto en Excel, ciérralo para que se pueda actualizar.

## Estados de una empresa

**Descubierta** → **Me interesa** → **Investigando** → **Contacté** → **Aplicado** → **Entrevista** →
**Oferta**, o **Descartada**. Cada cambio guarda la fecha y una nota opcional. Al pasar a *Contacté*,
*Aplicado* o *Entrevista* se agenda un recordatorio de seguimiento (5, 7 y 3 días); puedes cambiarlo.

## Vacantes de LinkedIn, Computrabajo o Indeed

Esos portales no se revisan automáticamente (sus reglas no lo permiten y piden iniciar sesión).
Si ves una vacante de una de tus empresas, copia el texto y pégalo en la conversación: se guarda como
evidencia de que esa empresa contrata en RD.

## Glosario

- **Presencia verificada**: hay al menos una fuente pública (enlace) de que la empresa opera en RD.
- **Equipo que encaja**: un área de la empresa donde tu perfil sirve (p. ej. supply chain, BI, ERP/SAP).
- **Rol probable**: un puesto que podría existir para alguien como tú en ese equipo, con su razón.
- **Señales de alerta**: cosas que podrían no convenirte (solo presencial, turnos, requisitos que no tienes).
- **Página de empleos**: la sección "Trabaja con nosotros" o "Careers" del sitio de una empresa.
- **ATS**: el sistema que muchas empresas usan para publicar vacantes (Greenhouse, Lever, Workable…).
- **robots.txt**: un archivo donde cada sitio dice qué partes no deben revisar los programas. Se respeta.
- **Seguimiento**: el recordatorio para volver a escribir si no te han respondido.

## Preguntas frecuentes

**¿Me postula solo o envía mensajes por mí?**
No. Prepara los textos; tú decides si los envías y a quién.

**¿Por qué no hay una puntuación de 0 a 100?**
Porque una cifra da una falsa precisión. En su lugar ves los equipos, los roles probables con su
razón, la evidencia, tres razones y las señales de alerta, y decides tú.

**¿Dónde están mis datos? ¿Quién los ve?**
En tu computadora: el perfil en `~/.config/oportunidades-rd/` y lo demás en la carpeta `data/` del
proyecto. La investigación de empresas la hace tu asistente con sus búsquedas web. Si eliges una IA
con tu propia clave (Claude u OpenAI) para redactar, tu perfil y los datos de la empresa se envían
**solo** a ese proveedor. Con "ninguno", los textos son plantillas que editas tú.

**¿Cuesta dinero?**
El proyecto es gratis. Tu asistente de IA puede tener costo según tu plan, y si usas una clave de
API de Claude u OpenAI, pagas a ese proveedor según el uso.

**¿Por qué una empresa dice "abrir manualmente" o "revisar manualmente"?**
Es sobre sus vacantes: "revisar manualmente" significa que el sitio pide que los programas no lo
visiten (robots.txt); "abrir manualmente", que la página necesita JavaScript o iniciar sesión. En
ambos casos tienes el enlace para abrirla tú.

---

## Para usuarios técnicos

**oportunidades-rd** es una skill para agentes de IA (Claude Code, Codex y otros agentes
compatibles con `SKILL.md`) más una pequeña aplicación en Python: scripts de línea de comandos,
una base SQLite, un tablero Flask y exportación a Excel. El agente sigue [`SKILL.md`](SKILL.md):
descubre y analiza empresas con búsquedas web y las guarda con `scripts/empresas.py guardar`.

### Instalación manual

Requisitos: Python 3.10 o superior y `pip`.

**Claude Code (macOS / Linux)**

```bash
git clone https://github.com/alejandrocimentada/oportunidades-rd.git
mkdir -p ~/.claude/skills/oportunidades-rd
cp -R oportunidades-rd/. ~/.claude/skills/oportunidades-rd/
pip install -r ~/.claude/skills/oportunidades-rd/requirements.txt
```

**Claude Code (Windows PowerShell)**

```powershell
git clone https://github.com/alejandrocimentada/oportunidades-rd.git
New-Item -ItemType Directory -Force "$HOME\.claude\skills\oportunidades-rd" | Out-Null
Copy-Item -Recurse -Force "oportunidades-rd\*" "$HOME\.claude\skills\oportunidades-rd\"
pip install -r "$HOME\.claude\skills\oportunidades-rd\requirements.txt"
```

**Codex**

```bash
git clone https://github.com/alejandrocimentada/oportunidades-rd.git
mkdir -p ~/.codex/skills/oportunidades-rd
cp -R oportunidades-rd/. ~/.codex/skills/oportunidades-rd/
pip install -r ~/.codex/skills/oportunidades-rd/requirements.txt
```

Opcional, para redactar por API: `pip install anthropic` o `pip install openai`.

### Un recorrido completo, paso a paso

```bash
python scripts/perfil.py show                          # 1. sin perfil → el agente pregunta y guarda con `set`
python scripts/empresas.py contexto --json             # 2. perfil + empresas ya guardadas (para no repetir)
python scripts/empresas.py guardar --archivo empresas.json   # 3. el agente guarda lo que investigó
python scripts/rastrear.py                             # 4. ¿hay vacantes abiertas? (secundario)
python scripts/empresas.py list                        # 5. tú eliges
python scripts/empresas.py estado "Empresa X" "Me interesa"
python scripts/empresas.py generar "Empresa X" --rol "BI Analyst"   # 6. mensaje + carta (o el agente: guardar-texto)
python app.py                                          # 7. tablero en http://localhost:8765
python scripts/empresas.py estado "Empresa X" Contacté --nota "Escribí a Talent Acquisition"   # 8. seguimiento
```

Formato de `empresas.json` (una empresa o una lista):

```json
{
  "nombre": "Empresa X", "tipo": "multinacional", "industria": "zona franca/manufactura",
  "sitio_web": "https://empresa-x.com",
  "presencia_rd": "Planta en la Zona Franca de Haina.",
  "fuentes_presencia": [{"titulo": "Directorio de zonas francas", "url": "https://..."}],
  "equipos": ["Supply chain / planificación", "Mejora continua"],
  "roles": [{"rol": "Demand Planner", "razon": "2.5 años como Demand Planner con SAP."}],
  "evidencia": [{"texto": "Vacante de Planner publicada en 2026 en Haina", "url": "https://..."}],
  "razones": ["…", "…", "…"], "alertas": ["Mayormente presencial en planta."],
  "url_empleos": "https://empresa-x.com/careers", "portal_rd": "https://...?location=Dominican+Republic",
  "talento": "https://...", "linkedin_empresa": "https://www.linkedin.com/company/empresa-x",
  "roles_contacto": ["Gerente de Supply Chain", "Talent Acquisition"]
}
```

Tipos: `multinacional`, `grupo local`, `empresa local en crecimiento`, `tecnología/startup`, `otra`.
Sin `fuentes_presencia` con un enlace válido, la empresa **no se guarda**. Volver a guardar el mismo
nombre actualiza los campos que traiga.

Para probar sin tus datos: `python scripts/demo.py` y luego `python app.py --demo` (usa `data/demo/`).

Demo pública (GitHub Pages): `python scripts/construir_demo.py` escribe en `docs/` una copia estática del tablero
con datos inventados (sin servidor, no guarda nada). Vuelve a ejecutarlo cuando cambies `templates/` o `static/`;
en GitHub, Settings → Pages → rama `main`, carpeta `/docs`.

### Comandos

| Script | Para qué |
|---|---|
| `scripts/perfil.py show \| path \| set <clave> <valor> \| importar <yaml> \| ejemplo` | Perfil (listas separadas por `;`) |
| `scripts/empresas.py contexto \| guardar --archivo \| list \| show \| update \| remove` | Empresas y su análisis |
| `scripts/empresas.py estado \| nota \| seguimiento \| historial` | Seguimiento por empresa |
| `scripts/empresas.py generar <empresa> [--tipo] [--idioma] [--rol] \| guardar-texto` | Mensaje y carta |
| `scripts/rastrear.py [--empresa X] [--sin-detalles] [--sin-cache] [--novedades]` | ¿Hay vacantes abiertas? |
| `scripts/vacantes.py list [--empresa X] [--activas] \| show <id>` | Vacantes encontradas |
| `scripts/pegar.py --archivo f.txt [--url] [--empresa] [--titulo]` | Vacante copiada de un portal |
| `scripts/exportar.py` | Forzar el Excel |
| `app.py [--puerto 8765] [--no-abrir] [--demo]` | Tablero local |

### Cómo revisa las vacantes

- **robots.txt**: se lee para cada sitio; si una página está prohibida no se descarga ("revisar
  manualmente"). Un robots.txt que responde 401/403 se trata como "prohibido todo".
- **Ritmo**: máximo 1 petición cada 3 segundos por sitio. **Caché** de 24 h en `data/cache/`.
- **User-Agent**: `OportunidadesRD/0.1 (busqueda personal de empleo; respeta robots.txt; +https://github.com/alejandrocimentada/oportunidades-rd)`.
- **ATS públicos**: Greenhouse, Lever, Workable, SmartRecruiters, Teamtailor (también con región,
  p. ej. `empresa.na.teamtailor.com`) y BambooHR por su feed público; SAP SuccessFactors por su página
  pública de búsqueda.
- **HTML**: datos `schema.org/JobPosting` o enlaces que parecen vacantes. Descarta navegación ("Ver
  vacantes", "Aplica aquí"), postulaciones generales ("Envía tu CV") y categorías. Si la portada no
  tiene vacantes pero enlaza a la lista completa, la sigue una vez. Omite vacantes con ubicación
  explícita fuera de RD que no sean remotas.
- **JavaScript, login, anti-bots, 401/403/429**: "abrir manualmente", con el enlace. No se intenta saltar nada.
- **Portales bloqueados**: LinkedIn, Computrabajo, Indeed, Glassdoor, Bumeran y otros
  (`oportunidades/texto.py`) nunca se rastrean (sí pueden guardarse como enlace en `portal_rd`).

### Redacción con IA

`ia.proveedor` en el perfil: `agente` (por defecto: el agente investiga y redacta), `claude`
(`ANTHROPIC_API_KEY`, modelo por defecto `claude-sonnet-5-5`), `openai` (`OPENAI_API_KEY`, modelo por
defecto `gpt-5`; cámbialo con `set ia.modelo`) o `ninguno` (plantillas). A la API se envía solo el
perfil (sin rutas ni configuración) y los datos de la empresa, y únicamente al proveedor elegido.

### Datos

| Dónde | Qué |
|---|---|
| `~/.config/oportunidades-rd/profile.yaml` | Perfil (o `OPORTUNIDADES_RD_PROFILE`). El código se niega a guardarlo dentro del proyecto. |
| `data/oportunidades.db` | SQLite: `empresas`, `historial`, `vacantes`, `corridas` (o `OPORTUNIDADES_RD_DATA`) |
| `data/oportunidades.xlsx` | Excel regenerado tras cada cambio |
| `data/documentos/<id>-<empresa>/` | `mensaje.md` y `carta.md` |
| `data/cache/` | Páginas descargadas (24 h) |

`data/` y `profile.yaml` están en `.gitignore`. Para contactos solo existe la columna
`roles_contacto` (cargos); los roles que parecen un correo, un teléfono o un enlace se rechazan, y
ningún enlace puede ser el perfil de LinkedIn de una persona. Una base de datos de la versión anterior
(vacantes con puntuación) se respalda como `oportunidades.v1-<fecha>.db` y se empieza una nueva.

### Desarrollo y validación

```bash
pip install -r requirements.txt pytest
python -m pytest
```

Las pruebas usan páginas guardadas en [`tests/fixtures/`](tests/fixtures/) y nunca salen a internet.
Cubren la validación de empresas (fuente de presencia obligatoria, enlaces, sin datos personales), el
flujo de estados con historial y seguimientos, la redacción (adaptada al equipo y rol, solo al
proveedor elegido), el Excel, el tablero (solo localhost, cambios solo en JSON), que el perfil nunca se
guarde en el repo, y el rastreador (robots.txt, ritmo, caché, portales bloqueados, formatos y fallos
vistos en sitios reales).

### Límites conocidos

- **La calidad del descubrimiento depende del agente** y de su búsqueda web. Revisa las fuentes.
- **Sin vacantes publicadas no significa sin oportunidades**: por eso el centro es la empresa y la
  revisión de vacantes es secundaria.
- **El HTML genérico es heurístico**: cada sitio es distinto; las páginas hechas con JavaScript (p. ej.
  Oracle, Workday) se marcan para abrirlas tú.
- **Un solo usuario, una computadora**: no hay sincronización ni cuentas.

## Aviso

Proyecto independiente. No está afiliado a LinkedIn, Computrabajo, Indeed, Greenhouse, Lever,
Workable, SmartRecruiters, Teamtailor, BambooHR, SAP, Anthropic ni OpenAI. Las empresas de los
ejemplos y de la demostración son inventadas.

## Créditos: ESCO

> This service uses the ESCO classification of the European Commission.

El buscador de habilidades del paso 3 y parte de las sugerencias de habilidades y roles usan
**ESCO**, la clasificación europea de capacidades, competencias, cualificaciones y ocupaciones,
de la **Comisión Europea** (<https://esco.ec.europa.eu/es>), versión v1.2.1, con licencia
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es).

- **Versión adaptada:** `static/esco.json` no es ESCO completo. Lo hace `scripts/construir_esco.py` a partir de los
  CSV oficiales en español e inglés (solo conceptos publicados), con una lista de habilidades al estilo de un perfil
  profesional, nombres cortos en vez de frases de tareas:
  - **Subconjunto de ESCO:** los conocimientos («knowledge») de hasta 4 palabras que usa alguna ocupación, sin
    sufijos como «(programación informática)».
  - **Nombres reescritos:** las competencias transversales más usadas (40 o más ocupaciones), reescritas como
    nombre corto en `scripts/habilidades/competencias_esco.json` («gestionar proyectos» → «Gestión de proyectos»);
    las que no sirven como habilidad de perfil se quitan. Conservan su URI de ESCO.
  - **Habilidades curadas, que no son de ESCO:** herramientas y métodos actuales (Excel, Power BI, Salesforce, Scrum,
    ChatGPT…) y habilidades blandas, en `scripts/habilidades/curadas.json`; en el índice van marcadas `curada`.
  - Por ocupación, sus nombres y hasta 15 habilidades esenciales de esta lista. Los CSV originales (~95 MB) no se
    suben al repositorio.
- La Comisión Europea no respalda este proyecto. Según el aviso de copyright de ESCO, parte de su
  jerarquía de habilidades se basa en O\*NET OnLine (USDOL/ETA, CC BY 4.0) y en otras fuentes;
  este índice no incluye esa jerarquía, solo los nombres de las habilidades.
- Para actualizarlo: descarga la clasificación en <https://esco.ec.europa.eu/es/use-esco/download>
  (CSV, español e inglés; ESCO envía el enlace por correo), descomprímela en `data/esco/es` y `data/esco/en`
  y ejecuta `python scripts/construir_esco.py --origen data/esco/es --origen data/esco/en --version v1.2.1`, luego
  `python scripts/construir_demo.py`.

## Licencia

[MIT](LICENSE) © 2026 Alejandro Cimentada.
