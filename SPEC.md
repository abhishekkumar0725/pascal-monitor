# Pascal Web Logger — Product Spec

## 1. Overview

Pascal is a puppy. We currently log his activities (feeding, bathroom, sleep, training) via:

- `pascal_log.py` — terminal CLI (single user, on the Mac)
- `pascal_sync.py` — flushes Apple Notes "Pascal Queue" entries to CSVs

Both work but require either a terminal or Apple Notes. This project adds a third input channel: a **mobile-friendly web app** that anyone in the household can open on their phone and tap to log Pascal's activities. Multiple people, one source of truth.

### Primary goals
1. Multi-user input from any phone or laptop on the home network (and, later, anywhere).
2. **Minimum taps per entry** — the common cases (pee, poop, meal, water, sleep, wake) should be a single tap once the page is open.
3. Preserve the existing four CSVs as exportable artifacts, in their current schema, so `pascal_log.py` and any downstream analysis keep working unchanged.
4. Build the storage layer so flipping from local to cloud-hosted is a config change, not a rewrite.

### Non-goals (v1)
- Real authentication (passwords, OAuth, magic links).
- Push notifications / reminders.
- Photo uploads.
- Public sharing beyond the household.

---

## 2. Users & access model

**v1 (now): self-hosted on a Raspberry Pi on the home Wi-Fi.** A Raspberry Pi (4 or newer, 64-bit Raspberry Pi OS) sitting on the home network runs the FastAPI server as a long-lived `systemd` service so it stays up while no one is home. Phones reach it at `http://pascal.local:8000` (mDNS) or `http://<pi-lan-ip>:8000`. The Pi is the canonical host — the developer's Mac is only used for editing code and pushing it to the Pi (via `git pull` on the Pi or `rsync`). The Mac does not need to be on for logging to work.

Optional add-on: a free Cloudflare Tunnel running on the Pi gives a public URL for off-network logging without opening any router ports.

**v2 (later): cloud hosting.** Same code, deployed to Render / Fly / Railway. Storage backend swaps from local SQLite to managed Postgres or Supabase by changing only the `DATABASE_URL` env var. The Pi can either be retired or kept as a hot replica.

**User identification.** No real auth. The form has a `Logged by` dropdown (e.g., Abhishek / Partner / Walker / Other). The selection is sticky per-device via a cookie so it doesn't have to be re-picked every entry. The list of names is configured in `config.toml` (or `LOG_USERS` env var).

---

## 3. Tech stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn
- **Templating:** Jinja2 server-rendered HTML
- **Frontend interactivity:** HTMX (partial swaps after form submit — no full reloads, no SPA)
- **Styling:** Pico.css (classless) + a small `style.css`. No build step.
- **DB:** SQLite via SQLAlchemy 2.x (async). Single `pascal.db` file.
- **Migrations:** Alembic
- **Charts:** Chart.js via CDN, fed by a `/api/summary.json` endpoint
- **Tests:** pytest + httpx async client + an in-memory SQLite engine
- **Deps:** `uv` (preferred) with `pyproject.toml`; fallback `requirements.txt`
- **Lint/format:** `ruff`

The DB layer must be abstracted so `DATABASE_URL=sqlite+aiosqlite:///pascal.db` (default) can become `DATABASE_URL=postgresql+asyncpg://...` for v2 with no code changes.

---

## 4. Data model

### 4.1 Database — single `entries` table

A wide single table beats one table per category for v1: it dramatically simplifies "show today across categories" queries, edits, and the soft-delete model. Nullable columns are cheap. Normalize later only if categories explode.

| column         | type        | notes                                                                 |
|----------------|-------------|-----------------------------------------------------------------------|
| `id`           | INTEGER PK  | autoincrement                                                         |
| `category`     | TEXT NOT NULL | enum: `feeding` / `bathroom` / `sleep` / `training` / `walk` / `vet` / `spending` |
| `event_type`   | TEXT NOT NULL | meal / water / treat / pee / poop / accident / sleep / wake / nap / `<command>` / walk / med / etc. |
| `occurred_at`  | TIMESTAMP NOT NULL | when the event happened (user-supplied or `now()`); stored UTC |
| `logged_at`    | TIMESTAMP NOT NULL | when the row was inserted (server time, immutable)               |
| `logged_by`    | TEXT NOT NULL | name from dropdown                                                |
| `amount`       | TEXT        | feeding portion ("1 cup"); null for others                            |
| `location`     | TEXT        | bathroom location; null for others                                    |
| `command`      | TEXT        | training command name; null for others                                |
| `result`       | TEXT        | training: pass/fail/partial; null for others                          |
| `duration_min` | INTEGER     | walks; null for others                                                |
| `distance_km`  | REAL        | walks; null for others                                                |
| `cost_usd`     | REAL        | spending; null for others                                             |
| `notes`        | TEXT        | free-form, optional                                                   |
| `deleted_at`   | TIMESTAMP   | null = active; set on soft-delete                                     |
| `updated_at`   | TIMESTAMP NOT NULL | bumped on every edit                                              |

Indexes: `(occurred_at)`, `(category, occurred_at)`, `(deleted_at)`.

### 4.2 CSV exports

A `/export/<category>.csv` endpoint renders each category in the **exact column order `pascal_log.py` expects**, so dropping the file into the project folder is a no-op for any existing tooling:

- `feeding.csv`  → `timestamp, event_type, amount, notes`
- `bathroom.csv` → `timestamp, event_type, location, notes`
- `sleep.csv`    → `timestamp, event_type, notes`
- `training.csv` → `timestamp, command, result, notes`

Rules:
- `timestamp` = `occurred_at` formatted `YYYY-MM-DD HH:MM:SS` in local time (`America/New_York` by default; configurable).
- A separate `entries_full.csv` includes every column (incl. `logged_by`, `category`) for richer downstream analysis without breaking the legacy schema.
- Soft-deleted rows are excluded from CSV exports.
- Writes are atomic: write to `feeding.csv.tmp` then `os.replace()`.

Exposed as:
- `GET /export/{category}.csv` — single legacy CSV
- `GET /export/all.zip` — all four legacy CSVs zipped
- `GET /export/entries_full.csv` — full schema
- `make sync-csvs` (or `python -m app.scripts.export_csvs`) — writes all four into `CSV_EXPORT_DIR` (default = the parent Pascal project folder).

### 4.3 Future categories (schema-ready, not necessarily UI-built)

Walks, vet/medications, and spending fit into the same `entries` table by reusing the nullable columns. They can be added to the UI later without migrations. The schema reserves `duration_min`, `distance_km`, and `cost_usd` for this purpose.

---

## 5. API surface

**HTML routes** (return rendered pages or HTMX fragments):

| method | path                  | purpose                                                |
|--------|-----------------------|--------------------------------------------------------|
| GET    | `/`                   | home: 6 quick-tap buttons + "More…" + nav              |
| POST   | `/log`                | insert row, return success-toast fragment              |
| GET    | `/today`              | today's entries grouped by category                    |
| GET    | `/entries/{id}/edit`  | edit form fragment                                     |
| POST   | `/entries/{id}`       | update row (returns updated row fragment)              |
| DELETE | `/entries/{id}`       | soft-delete (returns empty fragment to swap)           |
| POST   | `/entries/{id}/undelete` | undo soft-delete                                    |
| GET    | `/summary`            | daily summary page with charts                         |

**JSON / data routes:**

| method | path                          | purpose                                            |
|--------|-------------------------------|----------------------------------------------------|
| GET    | `/api/summary.json?date=YYYY-MM-DD` | counts per category, last-meal, hours-since-last-pee |
| GET    | `/export/{category}.csv`     | CSV download in legacy schema                      |
| GET    | `/export/all.zip`            | zipped legacy CSVs                                 |
| GET    | `/export/entries_full.csv`   | full schema export                                 |
| GET    | `/healthz`                   | liveness probe                                     |

**Auth:** none in v1. All routes are open within the network. When v2 exposes the URL publicly, gate every mutating route behind a single shared-secret bearer token from `APP_TOKEN` env var; reads stay open or get the same gate, configurable.

---

## 6. UX

### 6.1 Home screen (mobile-first, the 80% case)

A 2×3 grid of large tap targets sized for a thumb on a phone:

```
┌──────────┬──────────┐
│   Pee    │   Poop   │
├──────────┼──────────┤
│   Meal   │  Water   │
├──────────┼──────────┤
│  Sleep   │   Wake   │
└──────────┴──────────┘
[ Logged by: Abhishek ▾ ]
[ More options… ]   (expands full form inline)
[ Today's log → ]   [ Summary → ]
```

Tapping a quick button:
1. POSTs `/log` with `category` + `event_type` filled in, `occurred_at = now()`, `logged_by = cookie value`, all other fields null.
2. Server returns an HTMX fragment that flashes "✓ Pee logged 12:04 PM" at the top for 3 seconds.
3. Optimistically refreshes a small "today" counter on the page.

**One tap** once the page is open. Two taps if the user wants to change `logged_by` first.

### 6.2 Full form (the "More options…" expansion)

Standard form, inline-revealed via HTMX so it's still on the home page:

`category` select → `event_type` select (options change with category) → `occurred_at` picker (default `now`, editable) → category-specific fields (amount / location / command / result / duration / distance / cost) → `notes` → submit.

### 6.3 Today screen

Reverse-chronological list of all entries today across categories. Each row: time · category icon · event_type · key field · `logged_by`. Tap a row → edit form fragment (uses the same `/entries/{id}/edit` endpoint). Tap 🗑 → soft-delete with an "Undo" toast for 5s.

Edits are **always allowed** on any row, no time window — including past days reachable via a simple date jump (`/today?date=YYYY-MM-DD`).

### 6.4 Summary screen

- Counts per category for today
- "Last meal: 2h 14m ago"
- "Last pee: 1h 03m ago"
- Bar chart: meals/pees/poops per day for the last 7 days (Chart.js)

---

## 7. Project layout

```
/Users/abhishekkumar/Documents/Claude/Projects/Pascal/
├── pascal_log.py           ← existing, do NOT modify
├── pascal_sync.py          ← existing, do NOT modify
├── feeding.csv             ← existing CSVs; web app exports OVER these on demand
├── bathroom.csv
├── sleep.csv
├── training.csv
├── spending - Sheet1.csv
├── SPEC.md                 ← this file
├── CLAUDE.md               ← Claude-Code-specific brief
└── web/                    ← new, all web-app code lives here
    ├── pyproject.toml
    ├── requirements.txt
    ├── README.md
    ├── config.toml         ← user names, port, CSV target dir, timezone
    ├── pascal.db           ← SQLite, gitignored
    ├── alembic.ini
    ├── alembic/
    │   └── versions/
    ├── app/
    │   ├── __init__.py
    │   ├── main.py         ← FastAPI app factory, route registration
    │   ├── config.py       ← Pydantic Settings, env + toml
    │   ├── db.py           ← async engine, session, Base
    │   ├── models.py       ← SQLAlchemy Entry model
    │   ├── schemas.py      ← Pydantic request/response
    │   ├── routes/
    │   │   ├── pages.py    ← HTML routes
    │   │   ├── entries.py  ← edit / delete / undelete
    │   │   ├── api.py      ← JSON routes
    │   │   └── export.py   ← CSV / zip export
    │   ├── services/
    │   │   ├── entries.py  ← CRUD + soft-delete + summary aggregation
    │   │   └── csv_export.py
    │   ├── scripts/
    │   │   ├── import_existing_csvs.py   ← one-shot seed from legacy CSVs
    │   │   └── export_csvs.py            ← invoked by `make sync-csvs`
    │   ├── templates/
    │   │   ├── base.html
    │   │   ├── home.html
    │   │   ├── today.html
    │   │   ├── summary.html
    │   │   ├── _entry_row.html       ← HTMX fragment
    │   │   ├── _quick_button.html
    │   │   ├── _full_form.html
    │   │   └── _toast.html
    │   └── static/
    │       ├── style.css
    │       └── icons/...
    ├── tests/
    │   ├── conftest.py
    │   ├── test_log.py
    │   ├── test_today.py
    │   ├── test_edit_delete.py
    │   ├── test_export.py
    │   └── test_summary.py
    └── deploy/
        ├── pascal-web.service       ← systemd unit for the Pi
        ├── install_on_pi.sh         ← idempotent Pi setup / upgrade script
        ├── cloudflared.example.yml  ← optional public-URL config
        └── README.md                ← Pi flashing → first boot → upgrade flow
```

---

## 8. Hosting

### 8.1 v1 — Raspberry Pi on home Wi-Fi (canonical)

Target hardware: Raspberry Pi 4 (or newer), 2 GB+, 64-bit Raspberry Pi OS, plugged into power and Ethernet (preferred) or Wi-Fi. The Pi must always be on; this is the whole point — logging works while the developer's Mac is asleep or out of the house.

Deliverables Claude Code must produce for the Pi:

- **`deploy/pascal-web.service`** — a `systemd` unit file. Runs uvicorn under a non-root `pascal` user, restarts on failure (`Restart=always`), starts at boot (`WantedBy=multi-user.target`), reads env from `/etc/pascal-web.env`, and binds to `0.0.0.0:8000`.
- **`deploy/install_on_pi.sh`** — idempotent setup script: installs system deps (`python3.11`, `python3-venv`, `sqlite3`, `git`), creates the `pascal` user, clones / pulls the repo into `/opt/pascal-web/`, sets up the venv, runs `alembic upgrade head`, installs the systemd unit, enables and starts it. Re-runnable for upgrades.
- **`deploy/README.md`** — one page covering: flashing the Pi, enabling SSH + mDNS, running the install script, finding the Pi on the network (`ping pascal.local`), reading logs (`journalctl -u pascal-web -f`), and the upgrade flow (`ssh pi@pascal.local 'cd /opt/pascal-web && git pull && sudo systemctl restart pascal-web'`).
- **`deploy/cloudflared.example.yml`** — optional Cloudflare Tunnel config to expose `pascal.<your-domain>` publicly without opening router ports.

Pi-specific behaviors:

- `CSV_EXPORT_DIR` defaults to `/opt/pascal-web/exports/` on the Pi (since the Mac's `/Users/abhishekkumar/Documents/Claude/Projects/Pascal/` is not reachable from the Pi). The developer pulls CSVs to the Mac via `scp pi@pascal.local:/opt/pascal-web/exports/*.csv ~/Documents/Claude/Projects/Pascal/` or by hitting `/export/all.zip` from the browser. A small `Makefile` target `make pull-csvs` automates this from the Mac.
- Backups: a nightly `cron` job on the Pi copies `pascal.db` to `/opt/pascal-web/backups/pascal-YYYY-MM-DD.db` and keeps the last 30. Optionally, `rsync` the backup dir to the Mac.
- Time: the Pi must run NTP (default on Raspberry Pi OS) so `occurred_at = now()` is trustworthy. Set the Pi's timezone to match `TIMEZONE` in `config.toml`.
- The Mac is **not** in the runtime path. Local dev still works on the Mac (`uvicorn ... --reload`), but production traffic goes to the Pi.

### 8.2 Cloud-ready (v2)

- All config from env vars with `config.toml` defaults: `DATABASE_URL`, `PORT`, `LOG_USERS`, `CSV_EXPORT_DIR`, `TIMEZONE`, `APP_TOKEN`.
- SQLAlchemy async engine with a URL discriminator → swapping to Postgres is one env-var change.
- No filesystem writes outside `pascal.db` and `CSV_EXPORT_DIR`. In v2 cloud, set `CSV_EXPORT_DIR=/tmp` and rely on `/export/all.zip` (or push to S3) for file delivery.
- Provide a `Dockerfile` (FastAPI + uvicorn, multi-arch so it builds for `linux/arm64` for the Pi and `linux/amd64` for the cloud).
- Provide a `Procfile` for Railway/Fly compatibility.
- Health check at `/healthz`.

---

## 9. Integration with existing scripts

The web app is purely **additive**. It does not edit `pascal_log.py`, `pascal_sync.py`, or the existing CSVs in place.

- The web app's source of truth is `pascal.db`.
- Calling `/export/all.zip` or `make sync-csvs` overwrites the four CSVs at the project root with the canonical export from the DB.
- A one-shot `scripts/import_existing_csvs.py` seeds `pascal.db` from the current CSVs on first run so historical data is not lost. After the import, the legacy CLI (`pascal_log.py`) and the web app are **two writers to two stores**. The pragmatic recommendation: pick the web app as the single writer going forward, and keep `pascal_log.py` for read/admin use only.
- See SPEC §11 for the documented collision policy if both write the same minute.

---

## 10. Milestones (suggested for Claude Code)

Each milestone has its own pytest module and must leave `main` runnable.

1. **M1 — Skeleton.** FastAPI app, SQLAlchemy + SQLite, Alembic init, `/healthz`, one-time CSV import script. Verifiable: `make seed && curl localhost:8000/healthz` returns 200; `sqlite3 pascal.db 'select count(*) from entries'` matches sum of legacy CSV row counts.
2. **M2 — Quick-log path.** Home page with 6 buttons, `POST /log`, sticky `logged_by` cookie, success toast. Verifiable: tapping each button on a phone writes a row visible in `sqlite3`.
3. **M3 — Today + edit/delete.** Today list, edit form, soft-delete with undo. Verifiable: edit a feeding row, delete a bathroom row, undo works, both reflected on refresh.
4. **M4 — CSV export.** Four legacy CSVs + `entries_full.csv` + zip endpoint + `make sync-csvs`. Verifiable: `head -1 <(curl -s localhost:8000/export/feeding.csv)` matches `timestamp,event_type,amount,notes`; round-trip import-export is lossless.
5. **M5 — Full form + new categories in schema.** "More options…" expansion; walk/vet/spending columns nullable in DB (no UI yet). Verifiable: insert a walk row via SQL, see it on `/today` with sensible default rendering.
6. **M6 — Summary + charts.** `/summary` page, `/api/summary.json`, Chart.js bars. Verifiable: bar heights match raw counts in DB.
7. **M7 — Pi deployment.** `deploy/` directory: `pascal-web.service`, `install_on_pi.sh`, `deploy/README.md`. Verifiable: running `bash deploy/install_on_pi.sh` on a clean Raspberry Pi OS image brings up the service such that `curl http://pascal.local:8000/healthz` from another machine on the LAN returns 200, and `sudo reboot` of the Pi leaves the service running afterwards.
8. **M8 — Polish.** Mobile CSS pass on a real phone, error states, 404 page, structured logging, nightly DB backup cron on the Pi, README with one-liner setup.

---

## 11. Open questions / decisions deferred

| topic                                         | default                                                              |
|-----------------------------------------------|----------------------------------------------------------------------|
| Timezone storage                              | Store UTC in DB, render local (`America/New_York`); configurable.    |
| Web ↔ CLI write collisions                    | Web export wins. No merge attempt. Documented.                       |
| `logged_by` in legacy CSVs                    | No — legacy CSVs unchanged for tooling compat. `entries_full.csv` carries everything. |
| Walks UI in v1?                               | Schema only in v1, UI in v2.                                         |
| Admin "wipe DB" endpoint                      | No. Use `alembic downgrade base && alembic upgrade head`.            |
| Backups                                       | `pascal.db` + nightly cron `cp` to a dated file in `web/backups/`. Out of v1 scope but trivial to add. |
| HTTPS on the local LAN                        | Skip in v1. Add via Cloudflare Tunnel when going public.             |
