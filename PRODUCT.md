# Product

<!-- impeccable:product-schema 1 -->

<!-- Written from the owner's redesign brief (2026-10-19) and README.md, without a separate init interview
     (the owner asked to proceed). Items marked (inferido) are inferences to confirm. -->

## Platform

web

## Users

Job seekers in the Dominican Republic, especially in AI integration, automation and data, often career-changers
who are not technical (the README targets "no necesitas saber programar"). The first real user is the owner: an
industrial engineer in Santo Domingo moving from retail demand planning into applied-AI roles. They open the local
dashboard a few times a week to see what is new, decide which postings deserve effort, and track applications.
Sessions are short and decision-oriented (inferido).

## Product Purpose

A personal, local job-search agent: it learns the user's profile, finds DR companies where they could work,
politely reads those companies' public career pages, scores every posting against the profile (0-100) with
reasons, red flags and skill gaps, and drafts an outreach message and cover letter only for postings the user
picks. Success: the user spends their limited energy on the few postings that truly fit, and never loses track
of an application or follow-up.

## Positioning

Everything runs on the user's own computer, and the tool is honest about fit: it shows why a posting fits, what
is missing and what is a red flag, instead of a match percentage with no reasons. It never applies, sends or
crawls job boards on the user's behalf; the user always decides.

## Operating Context

- Local Flask app on http://localhost:8765, opened by the agent (Claude Code) or by `python app.py`. Spanish UI.
- Data: profile in `~/.config/oportunidades-rd/profile.yaml`; SQLite in `data/`; Excel export regenerated on change.
- Pipeline states: Nuevo → Me interesa → Aplicado → Contacté → Entrevista → Oferta, plus Rechazado / Descartado.
- Crawl outcomes per company: ok, sin vacantes, revisar manualmente (robots.txt), abrir manualmente (JS/login/anti-bot),
  sin página, error.
- Scoring source shown per posting: heurística, agente, claude, openai.

## Capabilities and Constraints

- Views today: Mi perfil (form + "Guardar y buscar" with live progress), Resumen, Tablero (drag-and-drop kanban),
  Vacantes (filterable table), Empresas (contact ROLES with LinkedIn search links), detail drawer with status,
  follow-up date, reasons / red flags / gaps / "a conversar", message and cover-letter drafts, notes, history.
- All existing functionality and its tests must keep working in any redesign.
- Hard rules: no personal data about people (roles only); never send anything; never crawl LinkedIn/Computrabajo/Indeed.
- Runs only on localhost; no external accounts or servers. No external scripts are loaded today (inferido: keep it
  dependency-free and offline-capable).

## Brand Commitments

- Name: Oportunidades RD. Spanish-first copy, plain and friendly ("tú").
- Must have its own identity: NOT the owner's portfolio look (no grid paper, no #9BE28F green, no monospace-everywhere).
  The current UI uses #9BE28F and is being replaced.
- Desired feel (owner's words): calm, premium, trustworthy; effortless to see the best opportunities and act on them.

## Evidence on Hand

- Real profile (owner), 19 real companies with reasons, interest scores and contact roles, 4 crawled postings from
  Alegra (one is a navigation-link false positive, one a general "Envía tu CV" application), none scored yet.
- No testimonials, user counts or outcomes exist; never fabricate them. Sample postings used for layout must be
  clearly marked as samples.

## Product Principles

1. The user decides: the tool recommends and explains, it never acts on the user's behalf.
2. Honest over flattering: every score shows its reasons, red flags and gaps.
3. Calm focus: surface the few best opportunities first; everything else is one step away.
4. Private by default: local data, roles not people.

## Accessibility & Inclusion

Non-technical users: plain Spanish, no jargon in the UI. Status never by color alone; keyboard navigable (the
current app supports Esc to close the drawer and drag-and-drop with click fallback) (inferido: WCAG AA).
