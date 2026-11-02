# Student Budget Recipes

Final project for **72ITDS30103 – Software Development Platforms**. Team: Dung + _teammate_.

A student tops up a wallet, picks a day / week / month, and the app builds a lunch-and-dinner menu
that fits the budget, avoids foods the user cannot eat, and turns it into a shopping list.

## Features

- **Wallet** – top up any time; creating a menu takes its budget from the wallet.
- **Menu** – day, week or month, two meals a day, never over budget, skips excluded foods (allergies).
- **Price list** – ~100 sample supermarket items, editable. Plans are re-priced from it live.
- **Over budget** – when prices rise the user chooses: cheaper dishes or smaller portions. Nothing is swapped silently.
- **Mid-period top-up** – the app offers to upgrade the menu; past days stay, remaining days are rebuilt.
- **Shopping list** – whole plan or one week, same ingredients summed.
- **Substitutions (AI)** – Gemini suggests replacements for a missing ingredient. If the call fails
  (no key, rate limit, network) the list still works and a notice replaces the suggestions.
- **Recipes** – full create / edit / delete.

> Prices in `src/app/seed.py` are **sample prices**, not real supermarket prices.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --app-dir src --reload
```

Open http://127.0.0.1:8000. The first run creates `budget.db` (SQLite) and loads the sample data.

### Enable AI substitutions (optional)

Copy `.env.example` to `.env`, put your Gemini key in `GEMINI_API_KEY`, and start with:

```bash
uvicorn app.main:app --app-dir src --env-file .env
```

The key lives only in `.env` (git-ignored) and is sent from the server in a request header.

## Double-click launcher

`start.bat` creates `.venv` on first run, starts the app on a free port and opens the browser.
Put `.env` next to it for AI substitutions. Needs Python 3.12 on the machine.

A single-file `.exe` can be built with PyInstaller (`pyinstaller --onefile --name StudentBudgetRecipes
--paths src --add-data "src/app/templates;app/templates" --collect-submodules uvicorn run.py`),
but Windows Application Control blocks unsigned executables on some machines, so `start.bat` is the reliable route.

## Deploy to Render (free)

Render's disk is wiped on every restart, so the public site must use a hosted Postgres, not SQLite.

1. **Database:** create a free Supabase project and copy its **Session pooler** connection string
   (Render cannot reach Supabase's IPv6-only direct host).
2. **Web service:** on Render choose *New → Web Service*, connect this repo and set

   | Setting | Value |
   |---------|-------|
   | Runtime | Python 3 (version comes from `.python-version`) |
   | Build command | `pip install -r requirements.txt` |
   | Start command | `uvicorn app.main:app --app-dir src --host 0.0.0.0 --port $PORT` |
   | Instance type | Free |

3. **Environment variables** (Render dashboard, never in the repo): `DATABASE_URL` (the Supabase string)
   and `GEMINI_API_KEY`. Optional: `GEMINI_MODEL`.

The free instance sleeps after about 15 minutes idle, so open the URL a few minutes before a demo.
The app has no login: everyone who opens the URL shares one wallet.

## Test

```bash
pytest
```

## Layout

| Path | Contents |
|------|----------|
| `src/app/services.py` | Business rules (wallet, menu, budget fixes, shopping list) |
| `src/app/ai.py` | Gemini call and its failure handling |
| `src/app/main.py` | Web routes |
| `src/app/seed.py` | Sample prices and recipes |
| `tests/` | Rule tests and web smoke tests |

## Status

Offline version working. Docker, Compose, CI/CD and cloud deployment come next.
