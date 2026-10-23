# CareerAI — Career Recommendation System

A full-stack student project: a responsive career-exploration website backed by a
Python API. Students complete a five-step assessment (skills, interests, academics,
work preferences) and receive an explainable, rule-based ranked shortlist, a
skill-gap analysis, and career roadmaps.

The backend is authoritative. The original JavaScript engine is retained only for
an **explicit offline demo mode** and automated parity tests — it is never used as a
silent fallback.

> Match scores are **indicative profile matches, not probabilities of career
> success**. This is a transparent rule-based system, not a trained AI model.

## Project structure

The Git repository root contains the deployment configuration and the
`career-ai/` application folder:

```
<repo-root>/
├── render.yaml                # Render Blueprint (free single-service deploy)
├── .python-version            # Python 3.11.9 for Render/local tooling
├── .gitignore                 # venvs, caches, .env, disposable databases
└── career-ai/
    ├── index.html             # Page structure
    ├── style.css              # Responsive design system + API/demo states
    ├── careers-data.js        # Bundled catalog + label maps (demo/offline use)
    ├── recommendation-engine.js # JS engine (explicit demo mode + parity reference)
    ├── script.js              # UI, API integration, validation, modal
    ├── run-backend.bat        # Windows: create venv, install deps, start API
    ├── run-frontend.bat       # Windows: serve the site on port 5500
    ├── README.md
    └── backend/
        ├── app/
        │   ├── main.py        # FastAPI app, lifespan, CORS, frontend serving
        │   ├── config.py      # Environment configuration
        │   ├── database.py    # SQLAlchemy engine/session + SQLite directory
        │   ├── models.py      # Career ORM model
        │   ├── schemas.py     # Pydantic request/response models
        │   ├── catalog.py     # Loads the canonical catalog JSON
        │   ├── seed.py        # Idempotent seeding
        │   ├── data/careers.json # Canonical catalog (17 careers + label maps)
        │   ├── routers/       # health, careers, recommendations
        │   └── services/
        │       └── recommender.py # Python port of the scoring engine
        ├── tools/
        │   ├── export_catalog.py  # careers-data.js -> careers.json
        │   └── capture_fixtures.py# Receives browser-captured parity fixtures
        ├── tests/                 # Pytest suite (93 tests)
        ├── requirements.txt
        └── pytest.ini
```

`render.yaml`, `.python-version`, and `.gitignore` live at the repository root
because that is where Render looks for the Blueprint. The build and start
commands inside `render.yaml` therefore include the `career-ai/` prefix.

## Requirements

- Windows 10/11 (local scripts are `.bat`)
- Python 3.11 or newer (3.12/3.13 also work)
- A modern browser
- Internet access on first run (to install Python packages)
- For deployment: a free GitHub account and a free Render account

No API keys, paid services, external AI APIs, GPU, or authentication are used.
The deployed free service uses a disposable SQLite cache and no persistent disk.

## Quick start (Windows)

Open **two** terminals in the `career-ai` folder.

Terminal 1 — API:

```bat
run-backend.bat
```

This finds Python, creates `backend\.venv` if needed, installs
`backend\requirements.txt`, and starts Uvicorn at **http://127.0.0.1:8000**.
Swagger docs: **http://127.0.0.1:8000/docs**.

Terminal 2 — frontend:

```bat
run-frontend.bat
```

This serves the site at **http://127.0.0.1:5500**.

Open **http://127.0.0.1:5500** in your browser. The status banner should briefly
show “Career service connected”.

### Do not double-click `index.html` for the full app

Browsers do not give `file://` pages a normal HTTP origin, so API/CORS requests are
not reliable from a double-clicked file. Use `run-frontend.bat`. Opening
`index.html` directly still allows browsing the bundled **demo catalog**, but
recommendations require the API.

### Manual start (without the .bat files)

```bat
cd backend
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bat
cd career-ai
py -3 -m http.server 5500 --bind 127.0.0.1
```

### Single-origin production-style test (recommended before deploying)

This is the same architecture Render uses: FastAPI serves `index.html`, the CSS/JS
assets, the API, and `/docs` from one origin. Run it from the repository root:

```bat
career-ai\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir career-ai\backend --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. The frontend automatically uses same-origin
relative `/api/...` paths in this mode. API docs are at
**http://127.0.0.1:8000/docs**. If port 8000 is busy, use another port and open
that same port in the browser; no frontend URL override is needed because the
page and API share the origin.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Service status + seeded career count |
| GET | `/api/careers` | Catalog; supports `search`, `category`, `limit`, `offset` |
| GET | `/api/careers/{career_id}` | Full career profile (404 if unknown) |
| GET | `/api/careers/{career_id}/roadmap` | Learning roadmap from the stored profile |
| POST | `/api/recommendations` | Ranked matches for an assessment profile |

`POST /api/recommendations` accepts the exact profile the browser builds:

```json
{
  "name": "",
  "education": "bachelor",
  "branch": "computer-science",
  "percent": 85,
  "country": "",
  "skills": { "programming": 3, "design": 4, "writing": 4 },
  "interests": ["technology", "ai", "design"],
  "subjects": { "mathematics": 80, "computer-science": 70, "english": 85 },
  "workStyles": ["technical"]
}
```

- `education`, `branch`, skill/interest/subject/work-style keys and all ranges are
  validated with Pydantic. Invalid values return HTTP 422 with a readable reason.
- `name`, `percent`, and `country` are accepted to match the browser contract but
  **nothing from the request is persisted**.
- Insufficient profiles return `200` with `status: "insufficient"` and a message,
  not a fabricated ranking.

The response includes every ranked career with `score`, `components`,
`matchedSkills`, `matchedInterests`, `skillGaps`, human-readable `reasons`,
`weightsUsed`, `rank`, `topN`, and `coverage`.

## Recommendation engine

The authoritative implementation is `backend/app/services/recommender.py`, ported
from `recommendation-engine.js`:

| Component | Weight | Calculation |
|---|---|---|
| Skills | 40% | Sum of selected core-skill ratings (1–5 → 0.2–1.0) ÷ number of core skills |
| Interests | 25% | Shared interests ÷ `min(student interests, career interests)` |
| Academics | 20% | Weighted average of recorded subject marks over the career's relevant subjects |
| Preferences | 15% | Shared work styles ÷ `min(student styles, career styles)` |

- Missing components have their weight redistributed across the components that
  exist for that career.
- The final score is multiplied by `(0.5 + 0.5 × coverage)`, where `coverage` is the
  total weight of the sections the student completed — so an incomplete profile
  cannot score 100.
- Fewer than two sections → `status: "insufficient"`, no scores.
- Ranking order: score desc → skills component desc → title (`localeCompare`).
- The verified example is preserved: component scores **15 / 67 / 76 / 100**
  produce a final score of **53**.
- The overall percentage field is collected by the existing form but is not part of
  the original scoring rules; the academics component uses the per-subject marks.
  This behaviour is intentionally unchanged.

The JavaScript file is still loaded for the explicit demo mode; `tests/test_parity.py`
compares the Python engine against seven profiles captured from the real JS engine
in a browser, including every match's score, components, weights, matched/missing
skills, explanations, order, and rank.

## Career data

- `backend/app/data/careers.json` is the canonical backend catalog: all 17 existing
  careers plus label maps, education levels, and branches.
- It is generated from the frontend `careers-data.js` so content stays in sync:

  ```bat
  backend\.venv\Scripts\python.exe backend\tools\export_catalog.py
  ```

- Startup seeding is idempotent: missing careers are inserted, changed careers are
  updated, and reruns never create duplicates.
- The catalog also drives search and the detail/roadmap endpoints.

## Frontend behaviour

- Loads the catalog from `GET /api/careers` and renders the existing cards, filters,
  and search locally.
- Submits the assessment to `POST /api/recommendations`; prevents duplicate
  submissions while a request is pending.
- Shows a processing state, then renders through the existing result cards.
- On network/API failure: a clear error panel with **Retry** and an explicit
  **Use demo mode** button. Demo results are visibly labelled and never shown
  silently.
- Opens career details with `GET /api/careers/{id}`. If the API is unavailable, it
  shows the bundled profile with an “Offline demo copy” notice and a retry action.
- Preserves the existing keyboard navigation, focus management, Escape/backdrop
  modal dismissal, input validation, reset flow, and XSS-safe rendering.

### Configuration

| Setting | Default | How to change |
|---|---|---|
| API base URL | Same origin (`/api/...`) in production and when FastAPI serves the page; `http://<hostname>:8000` only when the frontend is served from local port 5500 | Set `window.CAREERAI_API_BASE` before `script.js` loads |
| Allowed CORS origins | `http://127.0.0.1:5500,http://localhost:5500` (local split-dev only) | Env var `CAREERAI_CORS_ORIGINS` (comma separated) |
| Database URL | `sqlite:///.../backend/careerai.db` locally; `sqlite:////tmp/careerai.db` on Render | Env var `CAREERAI_DATABASE_URL` |

Production uses one origin, so no CORS configuration is required for the deployed
site. CORS remains available for the optional two-terminal local workflow.

Example:

```bat
set CAREERAI_CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5173
run-backend.bat
```

## Tests

```bat
cd backend
.venv\Scripts\python.exe -m pytest
```

The suite uses a temporary SQLite database and covers:

- health, docs, and CORS behaviour
- single-origin serving of `/`, `index.html`, CSS/JS assets, and `/docs`
- blocked repository paths (`backend/`, database, README, `.gitignore`)
- catalog listing, search, category filters, pagination, detail, roadmap, 404s
- catalog preservation against the exported frontend data
- valid, insufficient, and empty assessments
- invalid marks, ratings, percentages, education/branches, unknown keys, duplicates
- deterministic rankings and profile-dependent ranking changes
- coverage scaling
- explanations and skill-gap correctness
- score parity with the browser-captured JavaScript outputs (direct + via the API)
- idempotent seeding and database/catalog equality
- absence of submission tables (no personal data stored)

Expected: **93 passed**.

To regenerate parity fixtures (optional, requires the JS engine in a browser):

1. Start the frontend at `http://127.0.0.1:5500`.
2. Start the collector: `backend\.venv\Scripts\python.exe backend\tools\capture_fixtures.py`.
3. In the browser console on the site, run the capture script that computes
   `CareerAI.RecommendationEngine.computeMatches(...)` for the profiles and
   `fetch("http://127.0.0.1:8770/fixtures", { method: "POST", mode: "no-cors", body: JSON.stringify(payload) })`.
4. Rerun `pytest`.

## Free Deployment on Render

### Architecture

CareerAI deploys as **one free Render Web Service**:

```
Browser
  └── https://<service>.onrender.com
        ├── GET /                      -> FastAPI returns career-ai/index.html
        ├── GET /style.css, /script.js -> FastAPI returns the existing assets
        ├── GET /docs                  -> FastAPI Swagger UI
        └── /api/*                     -> health, catalog, detail, recommendations
```

- The frontend and API share one origin, so production requests use relative
  `/api/...` paths and no cross-origin API URL.
- `render.yaml` at the repository root defines the service. The app itself stays
  in `career-ai/`; the build and start commands include that prefix.
- The SQLite database is a **disposable cache**. It is recreated and seeded from
  the version-controlled `career-ai/backend/app/data/careers.json` on every
  start. No student assessment submissions are stored.
- Render's free Web Service filesystem is ephemeral. No persistent disk or paid
  database is required.

### Required files

Commit these paths (and the rest of `career-ai/`):

- `render.yaml` — Blueprint, free plan, build/start commands, health check
- `.python-version` — `3.11.9`
- `.gitignore` — excludes `.venv`, caches, `.env`, and local `*.db` files
- `career-ai/` — frontend, backend, tests, and catalog data

Do **not** commit `career-ai/backend/.venv/`, `career-ai/backend/careerai.db`,
`.env` files, or credentials. The provided `.gitignore` already covers them.

### 1. Test locally first

From the repository root (the folder containing `render.yaml`):

```bat
career-ai\backend\.venv\Scripts\python.exe -m pip install -r career-ai\backend\requirements.txt
career-ai\backend\.venv\Scripts\python.exe -m pytest -q career-ai\backend\tests
```

Start the production-style single-origin app:

```bat
career-ai\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir career-ai\backend --host 127.0.0.1 --port 8000
```

Then verify:

- <http://127.0.0.1:8000/> loads the existing homepage.
- <http://127.0.0.1:8000/api/health> returns `status: "ok"` and `careers: 17`.
- <http://127.0.0.1:8000/docs> loads Swagger UI.
- Complete all five assessment steps and open a career detail modal.
- Refresh the homepage; the catalog should load again.

### 2. Create a GitHub repository and push

If Git is not installed, install it from <https://git-scm.com/downloads>. Create
an empty repository on GitHub (do not add a README there), then from the
repository root:

```bat
git status
git add render.yaml .python-version .gitignore career-ai
git commit -m "Prepare CareerAI for free Render deployment"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

If the remote already exists, use `git remote set-url origin <url>` instead of
`git remote add`. The explicit `git add` avoids publishing unrelated workspace
files.

### 3. Deploy with the Render Blueprint

1. Sign in at <https://dashboard.render.com/> with GitHub.
2. Choose **New +** → **Blueprint**.
3. Connect your GitHub account and select the repository you pushed.
4. Select the `main` branch and keep the Blueprint path as `render.yaml`.
5. Review the detected `career-ai` service (free plan) and choose **Apply**.
6. Render runs:
   - Build: `pip install -r career-ai/backend/requirements.txt`
   - Start: `uvicorn app.main:app --app-dir career-ai/backend --host 0.0.0.0 --port $PORT`
   - Health check: `/api/health`

The first deploy takes a few minutes. If the name `career-ai` is already taken,
change `name:` in `render.yaml`, commit, and sync the Blueprint again.

### 4. Find the public HTTPS URL

After the deploy succeeds, open the service in the Render Dashboard. The URL is
shown at the top, normally:

```text
https://career-ai.onrender.com
```

Render may append a suffix if the requested name is unavailable. Use the exact
URL shown in your dashboard; no URL is claimed here until your own deploy
succeeds.

### 5. Verify the deployed site

PowerShell:

```powershell
Invoke-RestMethod "https://<your-service>.onrender.com/api/health" | ConvertTo-Json
(Invoke-WebRequest "https://<your-service>.onrender.com/").StatusCode
(Invoke-WebRequest "https://<your-service>.onrender.com/docs").StatusCode
```

Expected health response includes:

```json
{
  "status": "ok",
  "service": "career-ai-api",
  "version": "1.0.0",
  "careers": 17
}
```

Then open the site in a browser and check the five-step assessment, results,
search, category filters, and a career detail modal. The API calls should target
the same `https://<your-service>.onrender.com` origin.

### 6. Inspect logs and redeploy

- **Build logs:** Render Dashboard → your service → **Logs** → **Build**.
- **Runtime logs:** same page → **Runtime**.
- **Deploy history:** **Events**.
- **Manual redeploy:** **Manual Deploy** → **Deploy latest commit**.
- **Automatic redeploy:** `autoDeploy: true` is set, so pushing to the connected
  `main` branch triggers a new build.
- **Blueprint changes:** edit `render.yaml`, commit, push, then use **Sync** on the
  Blueprint in the dashboard.

### Manual Dashboard alternative

If you prefer not to use a Blueprint:

1. **New +** → **Web Service** → connect the repository.
2. Set **Root Directory** to blank (repository root), **Runtime** to **Python 3**,
   and **Instance Type** to **Free**.
3. Build command: `pip install -r career-ai/backend/requirements.txt`
4. Start command: `uvicorn app.main:app --app-dir career-ai/backend --host 0.0.0.0 --port $PORT`
5. Health check path: `/api/health`
6. Add environment variables:
   - `PYTHON_VERSION=3.11.9`
   - `CAREERAI_DATABASE_URL=sqlite:////tmp/careerai.db`
7. Create the service and wait for the deploy.

If you set **Root Directory** to `career-ai` instead, remove the `career-ai/`
prefix from both commands.

### Free-tier behaviour and storage

- The free instance spins down after a period of inactivity. The next request can
  take tens of seconds while it wakes up. This is normal; no keep-alive job is
  configured.
- `/tmp/careerai.db` survives only for the life of the instance. On restart,
  redeploy, or wake-up, the app recreates the tables and seeds the same 17
  careers from `careers.json`. This is intentional.
- The app stores no names, marks, or assessment submissions. Every recommendation
  request is processed in memory and discarded.
- If durable user data is ever required, add a managed database; that is outside
  this free deployment and is not needed for the current read-only catalog.

## Troubleshooting

**“Python 3.11 or newer was not found”**
Install Python from <https://www.python.org/downloads/> and tick
“Add python.exe to PATH”. Alternatively edit `run-backend.bat` and set `PY_EXE` to
your interpreter's full path. Avoid the Microsoft Store placeholder alias.

**Port already in use (8000 or 5500)**

```bat
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

Or start Uvicorn on another port and open that same port in the browser. If you
are using the separate local static server on port 5500, set
`window.CAREERAI_API_BASE` to the API port instead.

**CORS error in the browser console (local split-dev only)**
The frontend origin must be allowed when the frontend is served from a different
origin (for example port 5500). Start the backend with
`CAREERAI_CORS_ORIGINS` set to the exact origin shown in the error (scheme, host,
and port). The deployed site uses one origin, so it does not need CORS.

**Banner says “Backend not connected”**
Start `run-backend.bat`, wait for “Uvicorn running on http://127.0.0.1:8000”, then
click **Retry connection**. Browsing still works with the bundled catalog.

**Render deploy returns 404 for the homepage**
Confirm that `render.yaml` is at the repository root, the build command is
`pip install -r career-ai/backend/requirements.txt`, and the start command is
`uvicorn app.main:app --app-dir career-ai/backend --host 0.0.0.0 --port $PORT`.
If you set a Render **Root Directory** of `career-ai`, remove the `career-ai/`
prefix from both commands.

**Render build fails on Python version**
`render.yaml` sets `PYTHON_VERSION=3.11.9`. You can change it to another
fully-qualified version supported by Render, such as `3.12.11`, if needed.

**Render health check fails**
Open **Logs** → **Runtime**. The startup log should say `Catalog ready` with
`career-ai-api` listening. Check that `CAREERAI_DATABASE_URL` is
`sqlite:////tmp/careerai.db` (four slashes) and that the health path is
`/api/health`.

**First Render request is slow**
Free services spin down when idle and cold-start on the next request. Wait for
the instance to wake up; do not add a keep-alive workaround.

**Database resets after a Render restart**
This is expected. The free filesystem is ephemeral; the app recreates and seeds
the catalog from `careers.json` on every start.

**`UnicodeEncodeError` in the console**
The scripts set `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1`. If running Python
manually from a path containing non-ASCII characters, set those variables first.

**Dependency installation fails**
Check your connection/proxy, then run:

```bat
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## Limitations

- The free Render service is ephemeral: SQLite is recreated and reseeded at
  startup, and the instance can spin down when idle.
- No authentication is included. The app is intended as a public, read-only
  career exploration prototype.
- The engine is rule-based and deliberately simple; it is not a predictive model.
- No salaries, employment statistics, or learning resources are invented — content
  comes from the existing 17 profiles.
- Assessments are stateless: refresh the page and the in-memory answers are gone.
