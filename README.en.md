[Español](README.md) · **English**

![Oportunidades RD](docs/banner.en.png)

Find companies in the Dominican Republic where you could work based on your profile, even if they
have no open postings today.

**[Try the demo](https://alejandrocimentada.github.io/oportunidades-rd/)** · [Install it](#how-to-use-it-the-easy-way)

## What it does

1. **You fill in your profile** with a few short questions (about 3 minutes).
2. **Your AI agent finds companies** in the DR that fit you. Each one comes with a source that
   confirms it operates there.
3. **It explains why they fit**: which teams, which roles you could have and how to apply.
4. **It checks whether they have open postings.**
5. **If one interests you**, it drafts a message and a letter. You decide whether to send them.

Everything stays on your computer. It never sends anything for you, never visits LinkedIn or other
job boards, and never stores other people's data.

The app's interface is in Spanish.

![A profile question](docs/captura-pregunta.png)

## How to use it (the easy way)

You need [Claude Code](https://code.claude.com/docs/en/quickstart), an AI assistant that works on your
computer. No programming needed.

1. Open Claude Code and paste this message:

   ```text
   Install the oportunidades-rd skill from https://github.com/alejandrocimentada/oportunidades-rd and open the panel for me.
   ```

2. Fill in your profile in the panel that opens in your browser.
3. Tell Claude Code: **"Find companies in the DR for my profile"**.

Then you can ask things like:

> Which teams at Company X fit me?
> Check whether these companies have open postings.
> Draft the message and letter for Company X.

Your companies and follow-ups are also kept in an Excel file (`data/oportunidades.xlsx`) that updates
itself.

## FAQ

**Does it cost money?** The project is free. Claude Code depends on your Claude plan.

**Where is my data?** Only on your computer: the profile in `~/.config/oportunidades-rd/` and the
companies in the project's `data/` folder.

**Why doesn't it score each company?** Because a number gives false precision. You see the reasons and
the red flags, and you decide.

**I saw a posting on LinkedIn or Computrabajo.** Those sites aren't checked automatically. Copy the text
and paste it to your agent: it's saved with that company.

---

## For developers

It's a skill for AI agents (Claude Code, Codex and others that support `SKILL.md`) plus a Python app:
command-line scripts, a SQLite database, a local Flask panel and the Excel export. The agent follows
[`SKILL.md`](SKILL.md).

<details>
<summary><b>Manual install</b></summary>

Requires Python 3.10 or later.

```bash
# macOS / Linux
git clone https://github.com/alejandrocimentada/oportunidades-rd.git
mkdir -p ~/.claude/skills/oportunidades-rd
cp -R oportunidades-rd/. ~/.claude/skills/oportunidades-rd/
pip install -r ~/.claude/skills/oportunidades-rd/requirements.txt
```

```powershell
# Windows (PowerShell)
git clone https://github.com/alejandrocimentada/oportunidades-rd.git
New-Item -ItemType Directory -Force "$HOME\.claude\skills\oportunidades-rd" | Out-Null
Copy-Item -Recurse -Force "oportunidades-rd\*" "$HOME\.claude\skills\oportunidades-rd\"
pip install -r "$HOME\.claude\skills\oportunidades-rd\requirements.txt"
```

For Codex, use `~/.codex/skills/` instead of `~/.claude/skills/`.

</details>

<details>
<summary><b>Commands</b></summary>

| Command | What it's for |
|---|---|
| `python app.py` | Profile panel at <http://localhost:8765> (your computer only) |
| `scripts/perfil.py show \| set <key> <value> \| sugerir` | View and change the profile |
| `scripts/empresas.py guardar --archivo empresas.json` | Save companies (each needs a source for its DR presence) |
| `scripts/empresas.py list \| show \| estado \| nota` | View companies and their follow-up |
| `scripts/empresas.py generar <company> --rol <role>` | Message and letter |
| `scripts/rastrear.py` | Check open postings (respects robots.txt, 1 request every 3 s per site) |
| `scripts/exportar.py` | Rebuild the Excel file |
| `scripts/construir_demo.py` | Rebuild the static demo in `docs/` |
| `python -m pytest` | Tests (no internet) |

</details>

## Credits: ESCO

> This service uses the ESCO classification of the European Commission.

Skill suggestions use [ESCO](https://esco.ec.europa.eu/en) v1.2.1, the European classification of
skills and occupations, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
**Adapted version:** we use a subset, with some names rewritten and curated skills that aren't from ESCO (details
in `scripts/construir_esco.py`). The European Commission does not endorse this project.

## License

[MIT](LICENSE) © 2026 Alejandro Cimentada. Independent project, not affiliated with the companies or job
boards it mentions.
