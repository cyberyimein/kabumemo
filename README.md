# Kabumemo (English Edition)

## Introduction

I originally leaned on Notion to keep track of trades, but the more I used it, the more I felt the tool was fighting me. I kept bending data into Notion’s format with elaborate workarounds. In an era where AI can even write test cases, I decided to hand the steering wheel to GPT‑5 Codex and vibe coding this project together.

Kabumemo isn’t revolutionary—just a straightforward CRUD app. I put it together over a weekend while gaming and guiding the AI, spending only a handful of tokens. Maybe soon anyone will be able to turn their specific needs into a product they can host on the cloud or on their own hardware. When AI and compute feel as ubiquitous as electricity and running water, everyone will share that ability to create.

## About Kabumemo

Kabumemo is an offline-friendly trading journal powered by a **Vue 3 + Vite frontend** and a **FastAPI backend**:

- **Frontend UI**: A tabbed dashboard (Trades, Positions, Funds, Tax) that lets you enter and review data directly in the browser.
- **Backend API**: Handles storage and business validation for transactions, funding groups, tax settlement, and exposes a unified REST interface.
- **Data storage**: JSON files are the primary source of truth, and every write is mirrored to a lightweight SQLite database (`kabumemo.db`). By default the app uses `data/`, but in production you can point everything at a fixed host directory such as `/path/to/kabumemo-data`.

The repository includes cross-platform startup scripts for macOS/Linux plus the older Windows batch files. The sections below provide the current development and deployment workflow.

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

### Quick start on macOS / Linux

Make the shell scripts executable once:

```bash
chmod +x start_kabumemo.sh start_kabumemo_prod.sh
```

Start the development stack:

```bash
./start_kabumemo.sh
```

This script will:

1. Create `backend/.venv` when missing.
2. Install backend dependencies when missing.
3. Install frontend dependencies when missing.
4. Start the backend at `http://127.0.0.1:8000`.
5. Start the frontend at `http://localhost:5173`.

To preview the production-style single-server mode locally:

```bash
./start_kabumemo_prod.sh
```

This builds `frontend/dist` and starts FastAPI directly, serving both `/` and `/api` from port `8000`.

If you need to pin the Python interpreter used to create `backend/.venv`, set `KABUMEMO_BASE_PY` first:

```bash
export KABUMEMO_BASE_PY="$(command -v python3)"
./start_kabumemo.sh
```

### Windows compatibility

Run `start_kabumemo.bat` from the repository root—double-click or launch it in a terminal—to automatically:

1. Detect or create the backend virtual environment and install dependencies.
2. Start `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` in a new window.
3. Install frontend dependencies (when needed) and start `npm run dev` in another window.

> Heads-up: The script uses UTF-8 output. When running from a shell, you can pass `--no-pause` to skip the final pause prompt.

### Simulate a production run (Windows)

Use `start_kabumemo_prod.bat` when you want to mimic a deployment build:

1. Ensure the backend virtual environment exists and install dependencies if missing.
2. Run `npm install` if needed and execute `npm run build` to emit `frontend/dist`.
3. Launch Uvicorn without auto-reload; FastAPI mounts `frontend/dist` at `/`, serving the compiled SPA alongside the `/api` endpoints. The server binds to `0.0.0.0` by default so other devices on your LAN can reach it, while the console still prints a clickable `http://127.0.0.1:8000` hint for local testing. Set `KABUMEMO_HOST` to another address if you need a different binding.

The console window stays open after shutdown so you can review logs; pass `--no-pause` if you want it to exit immediately.

Press `Ctrl+C` in the console to stop the server. Rerunning the script overwrites the existing `frontend/dist` output before starting the backend.

#### Choosing the Python interpreter for the virtualenv

Both batch scripts try, in order, to use:

1. A path you set via `KABUMEMO_BASE_PY`.
2. The Python that ships with `mamba`’s base environment (`mamba info --base`).
3. The first `python` available on your `PATH`.

If you want to pin the interpreter explicitly (for example, to mamba’s base env on Windows), set the environment variable before launching the script:

```bat
set KABUMEMO_BASE_PY=C:\mambaforge\python.exe
start_kabumemo_prod.bat --no-pause
```

The scripts log which interpreter they detected, so you can confirm the correct one is used when `.venv` is created.

### Start the backend manually

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

To override the data directory, set the `KABUCOUNT_DATA_DIR` environment variable:

```bash
export KABUCOUNT_DATA_DIR=/path/to/kabumemo-data
```

On Windows, use `set KABUCOUNT_DATA_DIR=D:\Kabumemo-data` instead.

Run tests:

```bash
cd backend
source .venv/bin/activate
python -m pytest
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

## Apple Container deployment

The macOS production environment uses Apple Container CLI. The root-level `Dockerfile.server` is a standard OCI build file that compiles the frontend and packages the backend into one image. Docker Desktop, Compose, and Colima are not required.

```bash
container build -t local/kabumemo-backend:latest -f Dockerfile.server .
container stop kabumemo-backend 2>/dev/null || true
container delete kabumemo-backend 2>/dev/null || true
container run --detach \
  --name kabumemo-backend \
  --publish 0.0.0.0:9527:8000 \
  --env KABUCOUNT_DATA_DIR=/data \
  --env KABUMEMO_DIST_DIR=/frontend_dist \
  --volume /Users/mithridates/data/kabumemo:/data \
  local/kabumemo-backend:latest
```

Production data is stored in `/Users/mithridates/data/kabumemo`, mounted at `/data` in the container. Its JSON files and `kabumemo.db` survive image rebuilds and container replacement.

To run the one-time JSON -> SQLite import inside the container:

```bash
container exec kabumemo-backend \
  python /app/backend/scripts/import_json_to_sqlite.py --data-dir /data --force
```

For the full deployment walkthrough, backup flow, and update commands, see `DEPLOY_MAC_SERVER.md`.

## Backend API Overview

| Method | Path                                 | Description                                                            |
| ------ | ------------------------------------ | ---------------------------------------------------------------------- |
| GET    | `/api/health`                        | Health check                                                           |
| GET    | `/api/transactions`                  | List all transactions                                                  |
| POST   | `/api/transactions`                  | Create a transaction, auto-generating a UUID and validating positions  |
| PUT    | `/api/transactions/{transaction_id}` | Update a transaction while enforcing funding group and position checks |
| DELETE | `/api/transactions/{transaction_id}` | Delete a transaction and clean up any related tax records              |
| GET    | `/api/positions`                     | Compute positions with per-currency breakdowns and realized P/L        |
| GET    | `/api/positions/history`             | Fetch 1-year daily price history plus buy/sell markers for a position  |
| GET    | `/api/funds`                         | Return fund snapshots plus currency-level aggregates and yearly ratios |
| GET    | `/api/funding-groups`                | List funding groups; creates JPY/USD on first launch                   |
| POST   | `/api/funding-groups`                | Create or overwrite a funding group                                    |
| PATCH  | `/api/funding-groups/{name}`         | Update a group’s currency, initial capital, or notes                   |
| DELETE | `/api/funding-groups/{name}`         | Delete a group (at least one must remain)                              |
| POST   | `/api/funding-groups/{name}/capital` | Schedule additional capital with an effective date per funding group   |
| POST   | `/api/tax/settlements`               | Record tax settlements, updating both funds and tax status             |

Every endpoint returns JSON, with errors exposing a `detail` field. `tests/test_api.py` exercises critical flows such as buying/selling, tax settlement, and deletion.

`GET /api/funds` responds with an object containing a `funds` array (per-group snapshots) and an `aggregated` array (currency-level rollups with year-to-date and prior-year metrics), which the frontend renders side by side.

## Frontend Feature Overview

The UI uses tabs to organize primary workflows:

- **Trades**
  - Create or edit buy/sell transactions with automatic normalization of quantity and tax status; the form shows an inline editing state with cancel/save controls.
  - Click any row to prefill the form for rapid re-entry, or use the action column to edit/delete with confirmation without losing the quick-entry workflow.
  - A refresh button pulls the newest data from the backend.
- **Positions**
  - Calculates holdings with per-currency quantity/average-cost breakdowns, including realized P/L.
  - Adds a single-select history view that shows 1-year daily prices with buy/sell markers (ECharts).
- **Funds & Groups**
  - Manage funding groups (create, edit, delete) and visualize detailed fund snapshots with year-over-year metrics.
  - View currency-level aggregates to compare overall cash, holdings, and profitability across groups, now with an inline USD→JPY exchange-rate input that converts the merged summary into JPY in real time.
  - Add capital injections with a specific effective date; future-dated contributions are stored but excluded from the current-year yield until the date arrives.
  - Browse a paginated capital addition log that lists every contribution, highlights future-dated entries, and mirrors the backend’s `/funding-groups/capital` feed for auditability.
  - Deletion checks that at least one group remains; all copy is localized.
- **Tax**
  - Automatically lists sell trades whose tax status is still pending.
  - Submit a tax amount/exchange rate to mark the trade as taxed and refresh fund snapshots.

The interface supports Chinese, English, and Japanese. The notification bar announces results after refresh, create, or delete actions.

## Data Files

- `transactions.json`: Transaction history, created on first API use.
- `funding_groups.json`: Funding group definitions; JPY and USD groups are generated on first run.
- `tax_settlements.json`: Maintained by the tax settlement API.
- `capital_adjustments.json`: Effective-dated capital additions per funding group.
- `kabumemo.db`: SQLite mirror that stays in lockstep with the JSON files and powers structured queries or external tooling. Delete it to force a JSON -> SQLite rebuild.
- `data/backups/`: Reserved for future backup tooling.

### Maintenance scripts

- `backend/scripts/import_json_to_sqlite.py`: Run once after upgrading to the dual-storage backend (or anytime you need to rebuild the database) to mirror JSON data into SQLite. Pass `--force` to overwrite existing tables.
- `backend/scripts/check_data_sync.py`: Compares JSON and SQLite content; exits with a non-zero status when any record is missing or diverges. Combine with CI or cron to flag drift quickly.
- `backend/scripts/rebuild_data_from_broker_csv.py`: Rebuilds transactions and realized P&L from the UTF-8 broker export files under `realdata/export/`. Keep this script for disaster recovery or clean-room rebuilds after replacing the live data set.

Example usage from the repository root:

```bash
python backend/scripts/import_json_to_sqlite.py --data-dir ./data
python backend/scripts/check_data_sync.py --data-dir ./data --verbose
python backend/scripts/rebuild_data_from_broker_csv.py --data-dir ./data
```

## Roadmap

- Extend trading features: bulk import/export, advanced filters.
- Broaden test coverage for multi-currency and cross-group edge cases.
- Provide backup/restore utilities (CSV/ZIP).
- Explore packaging into a desktop shortcut or single-file binary.

## Recent Work — 2025-10-22

- **Capital history log**: Added `/api/funding-groups/capital`, expanded the tests, and exposed a localized table on the Funds tab with pagination plus scheduled/future badges so every addition stays visible.
- **Round-trip yield analytics**: Added a dedicated FastAPI route (`POST /api/transactions/round-yield`) and the underlying `compute_round_trip_yield` service to reconcile matching buy/sell transactions, surface gross/net profit, tax impact, and annualized returns. Expanded Pydantic schemas and backend tests to cover happy path and validation failures.
- **Trades tab enhancements**: Introduced “Round Trip Yield” mode with multi-select checkboxes, a live selection summary card, validation messaging, and an analytics modal that highlights all computed metrics. The calculate button remains accessible even when selections are invalid, while warnings are routed through the global notification bar.
- **UX + localization polish**: Refreshed button sizing, color palette, and card layout, localized all new copy in English/Japanese/Chinese, and ensured assistive technologies receive alerts only after an explicit calculation attempt.
- **Quality gates**: Verified changes with `pytest` on the backend and `npm run build` (includes `vue-tsc`) on the frontend to keep the bundle and analytics pipeline stable.

## Recent Work — 2025-10-07

- **Dual storage rollout**: The repository now mirrors every write to both JSON and a SQLite database, with transactional safeguards in `LocalDataRepository` and helper accessors to query either source.
- **Tooling refresh**: Added `import_json_to_sqlite.py` for one-time migrations and `check_data_sync.py` to catch drift between stores. Tests assert JSON/SQLite parity on critical workflows.
- **Container pathway**: Introduced `backend/Dockerfile` plus documentation so the backend can run inside Docker on macOS with a bind-mounted `/data` volume.
- **Docs & tests**: Updated the READMEs, clarified the `KABUCOUNT_DATA_DIR` override, and extended the pytest suite to validate SQLite mirroring during lifecycle flows.

### 2025-10-03

- **Positions analytics refresh**: The backend `analytics` service now computes per-funding-group breakdowns for each holding, with matching schema updates and regression tests to keep historical scenarios covered.
- **UI expansion**: Positions rows can be expanded to reveal group-level metrics, providing quantity, cost, and realized P/L visibility without leaving the table.
- **Pagination everywhere**: Introduced a reusable `usePagination` composable and `PaginationControls` component, then wired them into the Trades, Positions, Funds, and Tax tabs so large datasets stay fast and scannable (50 rows per page by default).
- **Localized copy**: Added English/Japanese/Chinese strings for the new pagination controls to keep the tri-language experience consistent.
- **Quality gates**: Verified changes with the existing pytest suite and `npm run build` to ensure analytics logic and the Vue bundle remain healthy.
