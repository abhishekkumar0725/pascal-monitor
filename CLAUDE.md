# CLAUDE.md — Pascal Web Logger

This file briefs Claude Code on project conventions, development commands, and what NOT to touch. The product spec is in `SPEC.md` — **read it first**, before any code is written.

## Project at a glance

A FastAPI + HTMX web app for logging puppy activities. Lives in `web/` inside the larger Pascal project folder. Source of truth = `web/pascal.db` (SQLite). Existing CLI tooling (`pascal_log.py`, `pascal_sync.py`) and the four legacy CSVs at the project root are untouched by app code; they are read once during initial seeding and overwritten only via the explicit `/export` endpoints / `make sync-csvs` target.

**Production target = a Raspberry Pi on the home Wi-Fi**, running the FastAPI server as a `systemd` service so it stays up while no one is home. The developer's Mac is for editing code only — runtime traffic from phones goes to the Pi at `http://pascal.local:8000`. See SPEC.md §8.1 for the deployment contract (`deploy/pascal-web.service`, `deploy/install_on_pi.sh`, `deploy/README.md`).

## First-time setup

### Local dev (on the Mac)

```
cd web
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.import_existing_csvs   # one-shot seed from legacy CSVs
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser to iterate.

### Production (on the Raspberry Pi)

From a fresh Raspberry Pi OS install with SSH enabled:

```
ssh pi@pascal.local
git clone <repo> /opt/pascal-web
cd /opt/pascal-web
sudo bash deploy/install_on_pi.sh
```

The script installs system deps, creates a `pascal` service user, builds the venv, runs Alembic, installs and starts the systemd unit, and prints the LAN URL. After that, phones on the home Wi-Fi reach the app at `http://pascal.local:8000`.

Upgrades (after pushing new code to the repo):

```
ssh pi@pascal.local 'cd /opt/pascal-web && git pull && sudo systemctl restart pascal-web'
journalctl -u pascal-web -f   # tail logs
```

## Daily commands

| task                            | command                                                                  |
|---------------------------------|--------------------------------------------------------------------------|
| dev server                      | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`               |
| tests                           | `pytest -q`                                                              |
| lint + format                   | `ruff check . && ruff format .`                                          |
| new migration                   | `alembic revision --autogenerate -m "<msg>"` then `alembic upgrade head` |
| regenerate CSVs into parent dir | `python -m app.scripts.export_csvs` (or `make sync-csvs`)                |
| pull CSVs from the Pi to Mac    | `make pull-csvs` (rsyncs `/opt/pascal-web/exports/*.csv` to project root)|
| tail Pi logs                    | `ssh pi@pascal.local 'journalctl -u pascal-web -f'`                      |
| restart Pi service              | `ssh pi@pascal.local 'sudo systemctl restart pascal-web'`                |

## Conventions

- Python 3.11+. **Type hints everywhere.** `from __future__ import annotations` at the top of every module.
- Async all the way down: async routes, async SQLAlchemy session.
- Pydantic v2 for request/response models.
- Templates use Jinja2 + HTMX. Avoid client-side state. **If you reach for React, stop and re-read SPEC.md §3.**
- One DB session per request via FastAPI dependency injection.
- Routes are **thin**. Business logic lives in `app/services/`.
- Tests use `httpx.AsyncClient` against an in-memory SQLite engine and a clean DB per test.
- Imports: stdlib → third-party → local, blank line between groups. `ruff` enforces this.
- Naming: snake_case for vars/functions, PascalCase for classes, SCREAMING for module-level constants.

## What NOT to touch

These are read-only references for the legacy schema. Do not modify:

- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/pascal_log.py`
- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/pascal_sync.py`
- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/feeding.csv`
- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/bathroom.csv`
- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/sleep.csv`
- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/training.csv`
- `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/spending - Sheet1.csv`

The four legacy CSVs may only be **overwritten** (atomically) by `app/services/csv_export.py` when the user invokes the export endpoint or `make sync-csvs`. The first-run seed script may **read** them but must not modify them.

## File-write etiquette

- All new application code lives under `web/`.
- `web/pascal.db`, `web/__pycache__/`, `web/.venv/`, `web/.pytest_cache/`, `web/.ruff_cache/` are gitignored.
- CSV exports use write-temp + `os.replace()` so partial writes never appear.
- No `print()` statements in committed code; use `logging`.
- No secrets in git. `config.toml` holds defaults; secrets come from env vars.

## Definition of done for each milestone

A milestone is not done until **all** of:

1. New code has tests covering the happy path and one failure mode.
2. `pytest -q && ruff check .` is clean.
3. `uvicorn app.main:app --reload` boots without errors and serves the home page.
4. The milestone's stated verifiable behavior in SPEC.md §10 works end-to-end.
5. SPEC.md is updated if any §11 "open question" was decided during the work.

## Anti-patterns to avoid

- Reaching for a heavier framework (Next.js, Django) "to make it easier later" — SPEC.md §3 is settled.
- Adding auth in v1 — out of scope. The shared-secret token is v2.
- Treating CSVs as the source of truth — DB is canonical; CSVs are exports only.
- One table per category — see SPEC.md §4.1 for why a single wide table is right here.
- Mutating the existing scripts or CSVs by hand.
- Writing JS beyond what HTMX needs. If a feature seems to need JS, ask whether HTMX or a server round-trip can do it instead.
- Hard-coding paths. Always read from `app.config.settings`. In particular, never assume `CSV_EXPORT_DIR` points at `/Users/abhishekkumar/...` — that path doesn't exist on the Pi.
- Coupling deployment to the Mac. The Pi is the runtime; the Mac is for editing. Don't write code that needs the Mac to be on.

## When unsure

Open SPEC.md §11 — the deferred-decisions list — and pick the documented default. If a question isn't covered there, leave a `# TODO(spec):` comment with a one-line description and continue. Surface the list of TODOs at the end of the milestone so the user can resolve them.

## Hand-off etiquette

At the end of each working session:
- Print a one-paragraph summary of what was done and what's left.
- List any new `TODO(spec):` markers added.
- Confirm whether `pytest` and `ruff` are clean.
