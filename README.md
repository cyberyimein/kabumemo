# Kabumemo (English Edition)

## Introduction

I originally leaned on Notion to keep track of trades, but the more I used it, the more I felt the tool was fighting me. I kept bending data into Notion’s format with elaborate workarounds. In an era where AI can even write test cases, I decided to hand the steering wheel to GPT‑5 Codex and “vibe code” this project together.

Kabumemo isn’t revolutionary—just a straightforward CRUD app. I put it together over a weekend while gaming and guiding the AI, spending only a handful of tokens. Maybe soon anyone will be able to turn their specific needs into a product they can host on the cloud or on their own hardware. When AI and compute feel as ubiquitous as electricity and running water, everyone will share that ability to create.

## About Kabumemo

Kabumemo is an offline-friendly trading journal powered by a **Vue 3 + Vite frontend** and a **FastAPI backend**:

- **Frontend UI**: A tabbed dashboard (Trades, Positions, Funds, Tax) that lets you enter and review data directly in the browser.
- **Backend API**: Handles storage and business validation for transactions, funding groups, tax settlement, and exposes a unified REST interface.
- **Data storage**: JSON files are stored under `data/` at the repository root, with optional overrides via environment variables.

The repository already includes a one-click startup batch script and end-to-end delete functionality for trades. The sections below provide a complete usage guide and feature overview.

## Project Structure

```plaintext
Kabumemo/
├── PLAN.md              # Planning notes and requirements
├── README.md            # Original documentation (Japanese/Chinese mix)
├── backend/             # FastAPI backend
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   └── storage/
│   ├── tests/           # pytest suites
│   └── pyproject.toml   # Backend dependencies
├── frontend/            # Vue frontend
└── data/                # Local data files and backups
```

## Quick Start

### One-click script (Windows)

Run `start_kabumemo.bat` from the repository root—double-click or launch it in a terminal—to automatically:

1. Detect or create the backend virtual environment and install dependencies.
2. Start `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` in a new window.
3. Install frontend dependencies (when needed) and start `npm run dev` in another window.

> Heads-up: The script uses UTF-8 output. When running from a shell, you can pass `--no-pause` to skip the final pause prompt.

### Start the backend manually

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

To override the data directory, set the `Kabumemo_DATA_DIR` environment variable:

```bash
set Kabumemo_DATA_DIR=D:\Kabumemo-data
```

Run tests:

```bash
cd backend
./.venv/Scripts/python.exe -m pytest
```

### Start the frontend manually

```bash
cd frontend
npm install
npm run dev
```

Build and lint:

```bash
npm run build   # Runs vue-tsc type-checking, then builds
npm run lint    # Optional: ESLint
```

Default development endpoints:

- Frontend: `http://localhost:5173`
- Backend: `http://127.0.0.1:8000`

## Backend API Overview

| Method | Path                                 | Description                                                           |
| ------ | ------------------------------------ | --------------------------------------------------------------------- |
| GET    | `/api/health`                        | Health check                                                          |
| GET    | `/api/transactions`                  | List all transactions                                                 |
| POST   | `/api/transactions`                  | Create a transaction, auto-generating a UUID and validating positions |
| DELETE | `/api/transactions/{transaction_id}` | Delete a transaction and clean up any related tax records             |
| GET    | `/api/positions`                     | Compute positions and realized P/L from transactions                  |
| GET    | `/api/funds`                         | Return fund group snapshots (initial capital, current total, P/L)     |
| GET    | `/api/funding-groups`                | List funding groups; creates Default JPY/USD on first launch          |
| POST   | `/api/funding-groups`                | Create or overwrite a funding group                                   |
| PATCH  | `/api/funding-groups/{name}`         | Update a group’s currency, initial capital, or notes                  |
| DELETE | `/api/funding-groups/{name}`         | Delete a group (at least one must remain)                             |
| POST   | `/api/tax/settlements`               | Record tax settlements, updating both funds and tax status            |

Every endpoint returns JSON, with errors exposing a `detail` field. `tests/test_api.py` exercises critical flows such as buying/selling, tax settlement, and deletion.

## Frontend Feature Overview

The UI uses tabs to organize primary workflows:

- **Trades**
  - Create buy or sell transactions with automatic normalization of quantity and tax status.
  - Click any row to prefill the form; the action column provides a delete button with confirmation that calls the DELETE API.
  - A refresh button pulls the newest data from the backend.
- **Positions**
  - Calculates holdings, average cost, and realized P/L directly from the transaction ledger.
- **Funds & Groups**
  - Manage funding groups (create, edit, delete) and visualize fund snapshots.
  - Deletion checks that at least one group remains; all copy is localized.
- **Tax**
  - Automatically lists sell trades whose tax status is still pending.
  - Submit a tax amount/exchange rate to mark the trade as taxed and refresh fund snapshots.

The interface supports Chinese, English, and Japanese. The notification bar announces results after refresh, create, or delete actions.

## Data Files

- `transactions.json`: Transaction history, created on first API use.
- `funding_groups.json`: Funding group definitions; default JPY and USD groups are generated on first run.
- `tax_settlements.json`: Maintained by the tax settlement API.
- `data/backups/`: Reserved for future backup tooling.

## Roadmap

- Extend trading features: editing, bulk import/export, advanced filters.
- Broaden test coverage for multi-currency and cross-group edge cases.
- Provide backup/restore utilities (CSV/ZIP).
- Explore packaging into a desktop shortcut or single-file binary.
