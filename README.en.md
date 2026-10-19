[Español](README.md) · **English**

![Oportunidades RD: find companies, review their openings and prepare your application](docs/banner.en.png)

<p align="center"><strong>An AI agent that helps you look for a job in the Dominican Republic: it finds companies where you could work, checks their career pages, tells you which openings fit you and why, and drafts your outreach message and cover letter. Everything runs on your computer, with a dashboard and a spreadsheet.</strong></p>

## What is this?

**Oportunidades RD** ("DR Opportunities") is a "skill" (a package of instructions and tools) that
you install in your AI assistant, such as Claude Code. Tell it *"find me AI jobs in the DR"* and it:

1. **Gets to know you**: the first time it asks a few questions (what you're looking for, your
   skills, your minimum salary) and saves your profile on your computer.
2. **Finds companies** in banking, telecom, retail/distribution, insurance, free-zone
   manufacturing, logistics, tourism, tech and government-tech. It explains why each one might
   suit you, even with no open positions, and which **roles** to contact (e.g. "Head of Data").
3. **Checks their career pages politely**: it follows each site's rules, goes slowly and never
   goes past a login.
4. **Scores how well each opening fits you** (0–100), with the reasons, the **red flags** (asks for
   7 years of experience, onsite only, pays below your minimum…) and **what you're missing**.
5. **You choose.** Only for openings you mark "Me interesa" (interested) does it draft a **short
   message** for LinkedIn or email and a **cover letter**, in Spanish or English depending on the posting.
6. **You stay on top of it** with a dashboard in your browser and an Excel file: what's new, where
   you applied, whom you contacted, when to follow up.

The app's interface is in Spanish.

## Who is it for?

Anyone looking for work in the Dominican Republic, especially in AI, automation and data (you can
change the target roles in your profile). You don't need to know how to code: the AI assistant
handles the technical part.

> [!IMPORTANT]
> **Everything stays on your computer.** Your profile, companies and openings are local files.
> There is no Oportunidades RD account or server.
> **Nothing is sent for you.** The message and the letter are saved as files; you review and send them.
> **It never crawls LinkedIn, Computrabajo or Indeed.** You copy and paste those postings (see below).
> **It stores no personal data about people.** For "who to contact" it only suggests **job titles**
> and gives you a LinkedIn search link that you open yourself.
> **The score is a guide, not the truth.** Read it critically, especially the no-AI heuristic.

## How to use it (the easiest way)

1. **Ask your AI assistant to install it.** If you use Claude Code or another AI agent (an assistant
   that can work with files on your computer), paste this message:

   ```text
   Install the oportunidades-rd skill from https://github.com/alejandrocimentada/oportunidades-rd
   ```

   <details>
   <summary><b>No AI agent yet? Start here (5 minutes)</b></summary>

   1. **What an AI agent is:** an assistant, like Claude Code, that can work with files on your
      computer: read them, run programs and explain the results.
   2. **Open the terminal** (the window where you type commands):
      - Windows: press the Windows key, type "PowerShell" and open it.
      - Mac: press Cmd + Space, type "Terminal" and open it.
   3. **Install Claude Code** following the [official quickstart](https://code.claude.com/docs/en/quickstart)
      (steps 1 and 2). You'll need a Claude account; the guide explains which plans include Claude Code.
   4. **Type `claude`** and press Enter. The first time it asks you to sign in. Then paste the message from step 1.

   </details>

2. **Answer a few questions the first time**: roles you want, skills and years of experience,
   languages, whether you want some remote days, your minimum salary in DOP, and your links. If you
   don't know something, say so and move on. Answers are saved in
   `~/.config/oportunidades-rd/profile.yaml`, outside the project folder.

3. **Ask for what you need**, in your own words:

   > Find companies in the DR where I could work on AI integration.
   > Check their career pages and tell me what's new.
   > Which openings fit me best? What am I missing for the TelcoX one?
   > Mark #12 as "Me interesa" and draft the message and cover letter.
   > I found this posting on LinkedIn: *(paste the text)*
   > Open the dashboard.

## The dashboard

Ask *"open the dashboard"*, or run `python app.py` in the project folder. It opens at
<http://localhost:8765> (only your computer can see it).

![Oportunidades RD dashboard with demo data](docs/captura-tablero.png)

- **Resumen** (summary): counts per status, applications this week, what's new since the last
  crawl, upcoming follow-ups and pages you should open yourself.
- **Tablero** (board): one column per status. **Drag a card** to change its status.
- **Vacantes** (openings): filter by fit score, company and status.
- **Empresas** (companies): interest score, career page and roles to contact with LinkedIn search links.
- **Detail panel**: why it fits, red flags, gaps, the message and letter with a **Copy** button,
  your notes and the dated history.

| Summary | Opening detail |
|---|---|
| ![Summary](docs/captura-resumen.png) | ![Detail](docs/captura-detalle.png) |

*(Screenshots use made-up companies and openings.)*

## The spreadsheet

`data/oportunidades.xlsx` is regenerated after every change, with four sheets (filters, frozen
headers, status colors): **Resumen**, **Empresas**, **Vacantes** and **Seguimiento** (every status
change with its date). Close it in Excel while making changes so it can be updated.

## Statuses

**Nuevo** (new) → **Me interesa** (interested) → **Aplicado** (applied) → **Contacté** (contacted) →
**Entrevista** (interview) → **Oferta** (offer), or **Rechazado** (rejected) / **Descartado** (dropped).
Each change is dated. Moving to Applied, Contacted or Interview schedules a follow-up (7, 5 and 3 days).

## Openings from LinkedIn, Computrabajo or Indeed

Those sites aren't crawled (their terms don't allow it and they require login). Copy the posting
text and paste it into the chat with your assistant, with the link if you have it. It's saved,
checked for duplicates and scored.

## FAQ

**Does it apply or send messages for me?** No. It drafts; you decide what to send and to whom.

**Where is my data, and who sees it?** On your computer: the profile in `~/.config/oportunidades-rd/`
and everything else in the project's `data/` folder. If you choose an AI provider with your own key
(Claude or OpenAI), your profile and the posting text are sent **only** to that provider for scoring
and writing. With the default ("agente"), your own assistant does that work. With "ninguno" (none),
nothing leaves your computer except the visits to career pages.

**Does it cost money?** The project is free. Your AI assistant may cost money depending on your plan,
and an API key from Claude or OpenAI is billed by that provider.

**Why does a company say "abrir manualmente" or "revisar manualmente"?** "Revisar manualmente"
means the site asks programs not to visit that page (robots.txt). "Abrir manualmente" means the
page needs JavaScript or a login. Either way you get the link to open it yourself.

---

## For technical users

**oportunidades-rd** is a skill for AI agents (Claude Code, Codex and other agents that support
`SKILL.md`) plus a small Python app: CLI scripts, SQLite, a Flask dashboard and Excel export. The
agent follows [`SKILL.md`](SKILL.md): it runs the web searches to discover companies and, in
`agente` mode, does the scoring and writing itself.

### Manual install

Python 3.10+ and `pip`. Same as the [Spanish README](README.md#instalación-manual): clone into
`~/.claude/skills/oportunidades-rd` (or `~/.codex/skills/…`) and `pip install -r requirements.txt`.
Optional, for API scoring/writing: `pip install anthropic` or `pip install openai`.

### A full run, step by step

```bash
python scripts/perfil.py show                      # 1. no profile → the agent asks and saves with `set`
python scripts/empresas.py add --nombre "Company X" --industria banca \
  --web https://x.com.do --empleos https://x.com.do/empleos \
  --por-que "..." --interes 80 --rol "Head of Data"            # 2. the agent discovers companies
python scripts/rastrear.py                         # 3. polite crawl + NOVEDADES (what's new)
python scripts/vacantes.py pendientes --json       # 4. (agent mode) the agent reads and scores…
python scripts/vacantes.py guardar-puntuacion 12 --ajuste 78 --encaja "..." --encaja "..." --encaja "..."
python scripts/pegar.py --archivo posting.txt --url https://... --empresa "Company X"   # 5. job-board postings
python scripts/vacantes.py estado 12 "Me interesa" # 6. you choose
python scripts/vacantes.py generar 12              # 7. message + letter (or the agent: guardar-texto)
python app.py                                      # 8. dashboard at http://localhost:8765
```

Try it without your data: `python scripts/demo.py`, then `python app.py --demo` (uses `data/demo/`).

### Crawling rules

robots.txt is honored (disallowed → "revisar manualmente"; robots.txt answering 401/403 → disallow
all); at most 1 request per 3 seconds per host; 24-hour cache in `data/cache/`; a descriptive
User-Agent (`OportunidadesRD/0.1 (…; respeta robots.txt; +https://github.com/alejandrocimentada/oportunidades-rd)`).
Public ATS feeds are used when the career page is, links to, or embeds Greenhouse, Lever, Workable,
SmartRecruiters, Teamtailor or BambooHR. Otherwise: `schema.org/JobPosting` JSON-LD, then
job-looking links (title, location, date), opening up to 10 detail pages per company. JavaScript-only
pages, logins, anti-bot pages and 401/403/429 → "abrir manualmente". Job boards (LinkedIn,
Computrabajo, Indeed, Glassdoor, Bumeran…) are blocked in both the crawler and `empresas.py`.
Duplicates: same URL without tracking parameters, or same company + title + location.

### AI providers

`ia.proveedor`: `agente` (default), `claude` (`ANTHROPIC_API_KEY`, default model `claude-sonnet-5-5`),
`openai` (`OPENAI_API_KEY`, default model `gpt-5`; change with `set ia.modelo`) or `ninguno`. With no
key, or if the API fails, a local heuristic is used (max score 95). Only the profile fields and the
posting text are sent, and only to the chosen provider.

### Tests

```bash
pip install -r requirements.txt pytest
python -m pytest                       # 79 tests, offline, using tests/fixtures/
```

### Known limits

- Company discovery quality depends on the agent's web search; check that career pages are official.
- Generic HTML extraction is heuristic; JavaScript-rendered pages aren't read (they're flagged).
- ATS feeds rely on known public endpoints that may change. SmartRecruiters and BambooHR lists have no description.
- The heuristic is basic (it can't tell "nice to have" from "required"); use agent mode or an API.
- Salary is only detected in DOP (RD$/DOP) or as a monthly amount near "salario".
- Single user, single computer. Not yet tested against real Dominican company sites in this repo.

## Disclaimer

Independent project, not affiliated with LinkedIn, Computrabajo, Indeed, Greenhouse, Lever, Workable,
SmartRecruiters, Teamtailor, BambooHR, Anthropic or OpenAI. Companies in screenshots and examples are made up.

## License

[MIT](LICENSE) © 2026 Alejandro Cimentada.
