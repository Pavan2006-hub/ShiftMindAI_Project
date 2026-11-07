# ShiftMind AI

Flask app for AI-assisted SRE incident response and persistent shift handover.

Features: login + roles, incident management, AI incident analysis (Groq), AI assistant chat,
long-term memory (Hindsight, optional), shift handover reports with PDF export.

## Credentials you need

Everything goes in ONE file: `.env` (same folder as `app.py`). Copy `.env.example` to `.env`.

| Variable | Required? | Where to get it |
|---|---|---|
| `SECRET_KEY` | **Yes** | Run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output |
| `GROQ_API_KEY` | **Yes for AI** (analysis, assistant, AI handover summary) | https://console.groq.com/keys (free, starts with `gsk_`) |
| `GROQ_MODEL` | No | Default `llama-3.3-70b-versatile` |
| `HINDSIGHT_API_KEY` | Optional (memory) | https://ui.hindsight.vectorize.io |
| `HINDSIGHT_BASE_URL` | Optional | Default `https://api.hindsight.vectorize.io` (use `http://localhost:8888` for a self-hosted server, no key needed) |
| `HINDSIGHT_BANK_ID` | Optional | Any name, default `shiftmind` |

Without Groq the app still runs; AI pages show a clear "not configured" message and handovers use a
rule-based summary. Without Hindsight the app runs normally, just without memory.

## Setup (Windows PowerShell)

```powershell
cd ShiftMindAI
py -3.9 -m venv .venv          # Python 3.9+ works
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env    # then edit .env
```

macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env`

## Database

```bash
flask --app app:create_app db upgrade        # creates / updates all tables
python -m database.create_admin              # first admin account (asks name/email/password)
```

An existing `instance/shiftmind.db` keeps working; `db upgrade` leaves it unchanged.

## Run

```bash
python app.py
```

Open http://127.0.0.1:5000 and sign in. Health check: `/api/health`.
New engineers are created by an admin in **Settings** (public sign-up is off unless
`ALLOW_PUBLIC_REGISTRATION=true`).

## Tests

```bash
python -m pytest
```

## Notes

- Never commit `.env`. Set `FLASK_ENV=production`, a strong `SECRET_KEY` and HTTPS (`COOKIE_SECURE=true`) for deployment.
- AI suggestions are unverified hypotheses; only record a root cause after an engineer verifies it.
