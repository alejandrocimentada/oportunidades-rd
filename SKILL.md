---
name: oportunidades-rd
description: Career agent for the Dominican Republic ("Oportunidades RD"). Builds the user's profile by asking questions, then discovers companies with a VERIFIED presence in the DR (multinationals with DR offices, regional hubs, shared-service centers or free-zone plants; large local groups; fast-growing local companies; tech companies and startups) where someone with that profile could work, whether or not they have open postings. For each company it records the matching teams, likely roles with reasons, evidence, why it fits, red flags, and how to apply (careers portal, talent pool, LinkedIn page, contact roles with people-search links). Tracks a per-company pipeline (Descubierta → Me interesa → Investigando → Contacté → Aplicado → Entrevista → Oferta / Descartada), drafts outreach messages and general application letters only for companies the user picks, politely checks career pages for open postings as a secondary signal, and shows everything in a local dashboard and an Excel file. Works for any user's profile. Use when the user wants to find where they could work in the DR, research a company, see what's new, or prepare an outreach. Never crawls LinkedIn/Computrabajo/Indeed, never scores with numbers, and never collects personal data about individuals.
---

# Oportunidades RD

Local career agent for the Dominican Republic. The unit is the **company**, not the posting:
many good places to work in the DR have no open posting today. Everything lives on the user's
computer: SQLite in `data/`, profile in `~/.config/oportunidades-rd/profile.yaml`. All paths below
are relative to this skill's directory. Requires Python 3.10+ (`python -m pip install -r requirements.txt`
if `python -c "import flask, bs4, openpyxl, yaml"` fails). Talk to the user in Spanish unless they
write in English; keep it simple, they may not be technical.

## Hard rules

- **Never** fetch LinkedIn, Computrabajo, Indeed, Glassdoor or similar job boards (not with web
  fetch, not with scripts). You may *link* to them (e.g. `portal_rd`, LinkedIn company page) for
  the user to open. Web *search results* that mention them are fine as leads; verify elsewhere.
- **Never** collect or store names, emails, phone numbers, personal profile URLs or any personal data
  of individuals. For "who to contact", save only ROLES (e.g. "Talent Acquisition", "Gerente de Supply
  Chain"); the app turns them into LinkedIn people-search links the user opens.
- **Never** add a company without at least one source link that verifies its presence in the DR.
  The script rejects it anyway. Don't invent facts, teams or evidence; say "no encontré evidencia".
- **No numeric scores.** Describe fit with teams, likely roles, reasons and red flags.
- **Never** bypass logins, CAPTCHAs or anti-bot pages, and never send anything on the user's behalf.
- The user's data goes only to the AI provider they chose (`ia.proveedor`). In `agente` mode you do
  the research and writing; don't paste their profile into other services.

## 0. Right after installing: open the panel

When you have just installed this skill (or the user asks to "abre el panel / el tablero"):

1. Install the requirements if needed: `python -m pip install -r requirements.txt`.
2. Start the dashboard **in the background** (it keeps running; don't wait for it to exit):
   `python app.py`. It serves http://localhost:8765 and opens it in the browser by itself. If the
   browser doesn't open (or you started it with `--no-abrir`), give the user that link.
3. Tell the user in one or two lines: the panel is open; they can build their profile there («Arma tu
   perfil»: about 11 short questions, one at a time, saved when they finish) or answer your questions
   here; then they can ask you «Busca empresas en RD para mi perfil».

If port 8765 is busy, the dashboard is probably already running: just give the link.

## 1. First run: build the profile

Run `python scripts/perfil.py show`. Exit code 2 means there is no profile yet. Either point the user
to the panel's survey (`python app.py`), or ask these questions (the same order as the panel's survey)
in one or two short messages, accepting "no sé" and moving on:

1. **Name** (`nombre`). Then, optional: **age** (`edad`) and **email** (`email`); both stay on this computer.
2. **Interests**: which areas they'd like to work in. Offer the list from `python scripts/perfil.py sugerir`'s
   map (tecnología, datos y análisis, finanzas y contabilidad, logística y cadena de suministro, operaciones y
   procesos, ventas, marketing, diseño, recursos humanos, salud, educación, servicio al cliente, legal,
   manufactura, turismo y hotelería); anything else goes in `intereses_otra`.
3. **Work experience?** yes / no (`tiene_experiencia`). If yes: years in their field (`anos_experiencia`),
   last or current job (`puesto_actual`) and (optional) a 2-3 sentence summary (`experiencia`).
4. **Studies** (`estudios`).
5. **Skills**: run `python scripts/perfil.py sugerir` and offer its `habilidades`; they pick and add their own.
6. **Roles**: offer the suggested `roles`; they pick, remove or add their own. If they don't know, set
   `roles_abiertos` to `si` and propose roles yourself when you research companies.
7. **Languages** with level (A1, A2, B1, B2, C1, C2 or Nativo), saved like «Inglés (C1)».
8. **Where and how**: city, modality (presencial / híbrido / remoto) and days (lunes a viernes or lunes a sábado).
9. **Minimum monthly salary** in DOP (optional; and whether startups may offer a different package).
   Drafting defaults to you (`ia.proveedor agente`); only change it if they ask for `claude`, `openai` or `ninguno`.

Save each answer (lists are separated by `;`):

```
python scripts/perfil.py set intereses "salud; educación"    ;  set intereses_otra "deportes"
python scripts/perfil.py set estudios "Licenciatura en Enfermería"
python scripts/perfil.py set puesto_actual "Enfermera en una clínica"   ;  set anos_experiencia 3
python scripts/perfil.py set experiencia "..."               # optional summary, used in letters
python scripts/perfil.py set habilidades "Habilidad 1; Habilidad 2"
python scripts/perfil.py set roles_objetivo "Rol 1; Rol 2"
python scripts/perfil.py set idiomas "Español (nativo); Inglés (C1)"
python scripts/perfil.py set ubicacion "Santo Domingo"
python scripts/perfil.py set preferencias.modalidad hibrido   # presencial | hibrido | remoto
python scripts/perfil.py set preferencias.dias_remotos 2   ;  set preferencias.dias "lunes a viernes"
python scripts/perfil.py set preferencias.salario_minimo_dop 100000
python scripts/perfil.py set preferencias.salario_flexible_startups true
python scripts/perfil.py set nombre "..."   ;  set titular "one-line professional headline"
python scripts/perfil.py set enlaces.linkedin https://...   (also enlaces.portafolio, enlaces.github)
python scripts/perfil.py set ia.proveedor agente      # agente | claude | openai | ninguno
```

**Refine the suggestions (optional, recommended).** The built-in suggestions come from a generic local
map (`oportunidades/sugerencias.json`, no AI). With the profile in hand you can do better: skills and roles
specific to *their* experience (e.g. "Analista de cuentas por pagar" for someone who did payables, not just
"Contador"), each with a one-line reason grounded in what they told you. Write a JSON file and save it:

```
python scripts/perfil.py sugerencias --archivo s.json   # {"habilidades": ["..."], "roles": [{"rol": "...", "razon": "..."}]}
python scripts/perfil.py sugerencias --borrar            # back to the built-in ones
```

The dashboard shows yours first, tagged «tu agente». Don't put them in `roles_objetivo` yourself: the
user picks.

Profiles from before v1.1 (with `industrias` and no `intereses`) are migrated automatically when loaded;
`industrias` is kept as an optional list of preferred sectors.

Then `show` again and confirm in one line. The script refuses to save the profile inside this folder.

## 2. Discover companies (you search the web)

Start with `python scripts/empresas.py contexto --json`: the profile plus the companies already saved
(don't repeat them unless updating). Work from **this user's** profile; nothing here is specific to
one person or field.

1. **Derive what to look for** from the profile: the functions their experience and skills fit
   (e.g. a demand planner with SAP → supply chain / planning, ERP / SAP, BI; a nurse → hospitals,
   clinics, health insurers, medical-device plants; a developer → tech companies, banks' digital
   teams, nearshore/outsourcing firms), their interests (`intereses`, `intereses_otra`), what they
   studied and their last job, their target roles, any preferred `industrias`, and their preferences
   (city, modality, schedule, language).
2. **Search broadly**, in Spanish and English, for companies operating in the DR in those areas:
   - multinationals with DR operations: offices, regional hubs, shared-service / BPO centers,
     free-zone plants (search free-zone directories, e.g. ADOZONA / CNZFE, and park tenant lists);
   - large local groups and fast-growing local companies (business press, rankings, sector associations);
   - tech companies and startups operating or hiring in the DR (startup ecosystems, tech news).
   Queries like: "<función> República Dominicana empresa", "centro de servicios compartidos Santo
   Domingo", "zona franca <industria> República Dominicana empresas", "<empresa> República Dominicana
   oficinas", "<empresa> Dominican Republic careers".
3. **Verify DR presence** for each candidate with at least one source link: the company's own page
   about its DR operation, a news article, a free-zone directory, an official registry, or a past/
   current DR posting on the company's own careers site. No source → don't add it.
4. **Match it to the profile** (no score):
   - `equipos`: the teams there that match (e.g. "Supply chain / planificación de demanda",
     "Transformación digital / innovación", "BI y analítica", "ERP / SAP", "Automatización", "TI").
   - `roles`: 2–4 likely roles for someone like this user, each with a short `razon` grounded in
     their actual experience and skills (write it about the user's experience, e.g. "2.5 años como
     Demand Planner con SAP", so it reads well in a letter).
   - `evidencia`: links showing those teams/roles exist in the DR when you can find them (past or
     current postings, team pages, news). Empty if none; don't invent.
   - `razones`: the 3 main reasons it fits. `alertas`: red flags (only on-site plant roles, shifts,
     requires skills the user lacks, no hybrid, salary signals below their minimum unless it's a
     startup and `salario_flexible_startups` is true — then say "a conversar" in a reason instead).
5. **How to apply**: `url_empleos` = the company's own careers page or public ATS page (crawlable;
   never a job board); `portal_rd` = careers portal filtered to the DR if the site allows it (may be a
   job-board link, it's only shown to the user); `talento` = talent pool / general application;
   `linkedin_empresa` = the company page (`linkedin.com/company/…`); `roles_contacto` = 2–3 job titles
   to contact (Talent Acquisition, the matched team's manager…).
6. **Save** a JSON file (one object or a list) in a temp folder and run
   `python scripts/empresas.py guardar --archivo <file>`. Re-saving the same name updates it. Format:

```json
{
  "nombre": "Empresa X",
  "tipo": "multinacional",
  "industria": "zona franca/manufactura",
  "sitio_web": "https://empresa-x.com",
  "presencia_rd": "Planta de dispositivos médicos en la Zona Franca de Haina.",
  "fuentes_presencia": [{"titulo": "Directorio de empresas de zonas francas", "url": "https://..."}],
  "equipos": ["Supply chain / planificación", "Mejora continua"],
  "roles": [{"rol": "Demand Planner", "razon": "2.5 años como Demand Planner con SAP y Excel."}],
  "evidencia": [{"texto": "Vacante de Planner en Haina (2026)", "url": "https://empresa-x.com/careers/123"}],
  "razones": ["...", "...", "..."],
  "alertas": ["Mayormente presencial en planta."],
  "url_empleos": "https://empresa-x.com/careers",
  "portal_rd": "https://empresa-x.com/careers?location=Dominican%20Republic",
  "talento": "https://empresa-x.com/talent-community",
  "linkedin_empresa": "https://www.linkedin.com/company/empresa-x",
  "roles_contacto": ["Gerente de Supply Chain", "Talent Acquisition"]
}
```

`tipo`: multinacional | grupo local | empresa local en crecimiento | tecnología/startup | otra
(`empresas.py tipos`). `industria`: see `empresas.py industrias`. Aim for a useful, varied list
(e.g. 15–25 companies) across the company types; quality over quantity. When done, tell the user
how many you added, grouped by type, and the 5 that fit best with one line each.

## 3. Open postings (secondary check)

`python scripts/rastrear.py` (or `--empresa "X"`) visits each company's `url_empleos`: robots.txt,
3 s between requests per site, 24 h cache, public ATS feeds (Greenhouse, Lever, Workable,
SmartRecruiters, Teamtailor, BambooHR, SuccessFactors search). Each company then shows "hay vacantes",
"no hay", or why it couldn't tell ("revisar manualmente" = robots.txt disallows; "abrir manualmente" =
needs JavaScript or login). Relay those links; don't fetch them another way. `--novedades` shows the
last run. The dashboard's "Guardar y revisar vacantes" button does the same. Postings are evidence,
not the goal: a company with "no hay" can still be a great target.

If the user pastes a posting from a job board, save it to a temp file and run
`python scripts/pegar.py --archivo <file> --url "<link>" --empresa "<company>"`.

## 4. Pipeline (per company)

Only change status when the user says so:
`python scripts/empresas.py estado "<empresa>" "Me interesa" [--nota "..."]`. States: Descubierta,
Me interesa, Investigando, Contacté, Aplicado, Entrevista, Oferta, Descartada. Each change is dated in
the history; Contacté/Aplicado/Entrevista schedule a follow-up (5/7/3 days;
`empresas.py seguimiento "<empresa>" AAAA-MM-DD` to change it). Notes: `empresas.py nota`.

## 5. Drafts (only for "Me interesa" or later, and only when asked)

A short outreach message (≤ 90 words, LinkedIn/email, no recipient name) and a general application
letter (250–350 words, not tied to a posting), both tailored to the matched team and one likely role,
and ending with the user's live work links (portfolio, GitHub). Spanish by default; English if the
company works in English or the user asks. Use only facts from the profile and the company record.

- `agente` mode: write them yourself, save each to a temp file, then
  `python scripts/empresas.py guardar-texto "<empresa>" --tipo mensaje --archivo <file>` (and `--tipo carta`).
- `claude`/`openai`: `python scripts/empresas.py generar "<empresa>" [--rol "..."] [--idioma en]`.
- `ninguno`: the same command creates a basic template the user must edit.

Files land in `data/documentos/<id>-<empresa>/`. Remind the user: nothing is sent automatically.

## 6. Panel and spreadsheet

- `python app.py` opens http://localhost:8765 (local only): the profile survey («Arma tu perfil»). It
  starts blank each time and saves the profile only when the user finishes. It no longer shows companies:
  show them in the conversation (`empresas.py list` / `show`) and point to the Excel file.
  `python app.py --demo` after `python scripts/demo.py` shows made-up sample data.
- `data/oportunidades.xlsx` (Resumen, Empresas, Vacantes, Seguimiento) is regenerated after every
  change; `python scripts/exportar.py` forces it. If Excel has it open, ask the user to close it.

## Routine ("¿qué hay de nuevo?")

`empresas.py list` → follow-ups due → `rastrear.py` and relay companies that now
have openings → offer to research more companies for the profile or to dig into one the user likes.
