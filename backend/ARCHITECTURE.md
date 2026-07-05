# Smart Job Assistant — Backend Architecture

> **What this is:** A FastAPI backend that automates job discovery and applications on
> **Naukri** and **LinkedIn**. It parses your CV, searches jobs, scores each one with an
> LLM, and either auto-applies (platform-native flows only), saves external jobs for you,
> or drafts a recruiter outreach email — all with account-safety guardrails (human pacing,
> rate caps, no CAPTCHA bypass).
>
> **Stack:** FastAPI + Uvicorn · SQLAlchemy + SQLite · Selenium (Chrome via CDP) ·
> OpenAI-compatible LLM clients (Azure / OpenAI / Gemini / Groq / OpenRouter) · pdfplumber.
>
> _Last updated: 2026-06-30._

---

## 1. The 10,000-foot view

```
                         ┌──────────────────────────────────────────┐
        Browser (React)  │  Vite dev server  http://localhost:5173   │
                         └───────────────┬──────────────────────────┘
                          REST + WebSocket │
                         ┌────────────────▼──────────────────────────┐
                         │  FastAPI app  (api/server.py)  :8001        │
                         │  ├─ routes/*  →  thin HTTP handlers         │
                         │  ├─ auth (JWT)                              │
                         │  └─ /ws  ←  live event stream               │
                         └───────┬──────────────────────┬─────────────┘
                                 │ start/stop           │ reads/writes
              ┌──────────────────▼─────────┐   ┌────────▼──────────────┐
              │  session_manager.py         │   │  SQLite DB             │
              │  (1 background worker thread)│   │  (api/models.py)       │
              │  ├─ builds Config + LLM      │   │  config, sessions,     │
              │  ├─ drives the job loop      │   │  applications, cv,     │
              │  └─ emits events → /ws       │   │  drafts, ignored, ...  │
              └───────┬─────────────┬────────┘   └────────────────────────┘
                      │             │
        ┌─────────────▼──┐   ┌──────▼───────────┐
        │ platforms/      │   │ core/             │
        │  naukri/        │   │  llm_client       │  scoring / chatbot / email
        │  linkedin/      │   │  cv_parser        │  PDF → structured CV
        │  (Selenium +    │   │  job_classifier   │  route by apply-flow
        │   Naukri API)   │   │  outreach         │  draft + (gated) send
        └────────┬────────┘   │  selectors        │  central CSS + health
                 │            │  tracker          │  logging + event emit
        ┌────────▼────────┐   └───────────────────┘
        │ Chrome (CDP)     │
        │ core/chrome_mgr  │
        └──────────────────┘
```

**One-line summary of the request flow:** the React UI calls REST endpoints; starting a
session hands work to a single background worker thread (`session_manager`), which drives
Selenium/HTTP against the job platforms, scores jobs with an LLM, writes every decision to
SQLite, and streams live progress back to the browser over a WebSocket.

---

## 2. How it boots & runs

Launched by [`run.sh`](../run.sh) at the repo root, which:

1. Kills stale processes on ports `5173/5174/5175/5176/8001`, clears the
   `webdriver-manager` lock, and kills leftover Chrome/chromedriver.
2. Creates/activates `backend/venv`, installs `requirements.txt`.
3. Runs `init_db()` to create tables + the singleton config row.
4. Starts the backend: `uvicorn api.server:app --host 0.0.0.0 --port 8001 --reload`.
5. Starts the frontend (`npm run dev`) on `:5173`.

The ASGI entrypoint is `api.server:app` → `create_app()`. On startup (`lifespan`):
`init_db()` runs, the **sync→async event relay** starts, and the tracker is wired to the
event queue. On shutdown it calls `session_manager.stop()`.

---

## 3. Folder & file map

```
backend/
├── api/                  ← Web layer: HTTP routes, DB models, auth, session orchestration
│   ├── server.py             FastAPI app factory + lifespan (startup/shutdown)
│   ├── database.py           SQLAlchemy engine, SessionLocal, init_db() + lightweight migrations
│   ├── models.py             10 ORM tables (Config, Session, Application, CVProfile, ...)
│   ├── schemas.py            Pydantic request/response models
│   ├── auth.py               JWT issue/verify + bcrypt password hashing
│   ├── event_queue.py        Bridges the sync worker thread → async WebSocket
│   ├── pipeline.py           DB-side state machine: status transitions, scoring gate, caps
│   ├── session_manager.py    ★ The orchestrator — runs the whole job loop in a worker thread
│   └── routes/               One module per endpoint group (see §5)
│       ├── auth.py  config.py  cv.py  session.py  history.py
│       ├── review.py  reports.py  ignored_jobs.py  ws.py  system.py  naukri.py
│
├── config/
│   └── settings.py           Runtime Config dataclass (the worker's in-memory config object)
│
├── core/                 ← Platform-agnostic brains
│   ├── llm_provider.py       Pick + validate an LLM provider (azure/openai/gemini/groq/openrouter/fuzzy)
│   ├── llm_client.py         LLM calls: score_job, answer_chatbot_question, draft_outreach_email
│   ├── fuzzy_client.py       No-AI fallback scorer (difflib string matching)
│   ├── cv_parser.py          PDF → CVData (LLM path or fuzzy path)
│   ├── job_classifier.py     Map page signals → classification → action (apply/save/draft/review)
│   ├── page_signals.py       Detect apply-flow signals from HTML (easy-apply, login wall, captcha)
│   ├── title_match.py        Hard keyword gate (discard off-target titles before any LLM call)
│   ├── date_filters.py       "posted within 24h/3d/7d/14d" filtering
│   ├── ignored_jobs.py       Persistent skip-list with auto-expiry + fingerprinting
│   ├── outreach.py           Compose recruiter email; SMTP send (triple-gated, never automatic)
│   ├── email_discovery.py    Extract recruiter emails from VISIBLE public job HTML only
│   ├── audit.py              Append-only AuditEvent log (log_event)
│   ├── evidence.py           Screenshot + page-text capture on failure
│   ├── tracker.py            Central logger + event emitter (file + stderr + WebSocket)
│   ├── selectors.py          Central CSS selector registry (ordered fallback lists)
│   ├── selector_health.py    Validate selectors vs DOM fixtures; track live drift incidents
│   ├── chrome_manager.py     Chrome lifecycle: attach / launch / capture-logging driver
│   └── statuses.py           Canonical status, classification & failure-reason vocabularies
│
├── platforms/            ← Per-site automation
│   ├── base_platform.py      Abstract contract + JobListing / JobDetails / ApplicationResult
│   ├── naukri/
│   │   ├── platform.py           Orchestrates Selenium ↔ API modes
│   │   ├── login.py              Username/password Selenium login + session detection
│   │   ├── search.py             Selenium search-results scraping (React cards)
│   │   ├── job_scraper.py        Selenium JD-page detail extraction
│   │   ├── apply.py              Internal apply (chatbot drawer) + external-URL capture
│   │   ├── api_search.py         HTTP search API (reCAPTCHA-gated, token auth) — SEARCH ONLY
│   │   └── token_capture.py      Auto-harvest cookie + nkparam via Chrome CDP performance log
│   └── linkedin/
│       ├── platform.py  login.py  search.py  job_scraper.py  apply.py   (Selenium only)
│
├── utils/
│   ├── rate_limiter.py       Per-hour/day caps + randomized human pacing delays
│   └── retry.py              Selenium retry decorator for transient errors
│
├── tests/                ← pytest suite + DOM fixtures (see §9)
├── data/                 ← SQLite DB, CV uploads, Chrome profiles, failure evidence
├── logs/                 ← tracking.log + applications.json
└── requirements.txt
```

---

## 4. The data model (`api/models.py`)

SQLite, one file at `data/smart_job_assistant.db`. `init_db()` creates tables and runs
**idempotent column-add migrations** on every boot (so adding a config field never needs a
manual migration). Ten tables:

| Table | Purpose | Notable fields |
|---|---|---|
| `users` | App login accounts | email, `hashed_password` (bcrypt) |
| `config` | **Singleton (id=1)** — replaces `.env` | platform creds, LLM keys, `naukri_search_mode`, `naukri_cookie/nkparam`, rate caps, safety toggles |
| `cv_profiles` | Parsed résumé(s); `is_active=True` is current | skills[], job_titles[], experience_years, summary, `pdf_path` |
| `sessions` | One job-search run | platform, mode, job_target, threshold, keywords[], counters, status |
| `applications` | One job evaluated/applied | score, status, classification, failure_reason, LLM rationale, skills, evidence_path |
| `ignored_jobs` | Skip-list for future runs | `job_fingerprint` (URL or platform+company+title), expiry, ignore_type |
| `outreach_drafts` | Recruiter email drafts | recruiter_email, subject, body, status (draft→approved→sent) |
| `outreach_send_log` | Immutable record of every send | recipient, method (smtp / user_mail_client) |
| `audit_events` | Append-only session event log | event_type, JSON `detail` |

**Two different "Config" objects** — don't confuse them:
- `api/models.py::Config` — the **persistent DB row** the UI edits.
- `config/settings.py::Config` — an **in-memory dataclass** the worker builds at session
  start (from the DB row) and passes around to platforms/LLM clients.

---

## 5. Web layer — routes (`api/routes/`)

All endpoints require a JWT except `/api/auth/check-setup` and `/api/health`.

| Group | Key endpoints |
|---|---|
| **auth** | `POST /api/auth/signup` · `POST /api/auth/login` · `GET /api/auth/me` · `GET /api/auth/check-setup` |
| **config** | `GET /api/config` (secrets masked) · `PUT /api/config` · `POST /api/config/test` (live LLM ping) |
| **cv** | `POST /api/cv/parse` (upload PDF) · `GET/PUT /api/cv/profile` · `POST /api/cv/ats-analyze` · `POST /api/cv/suggest-keywords` |
| **session** | `POST /api/session/start` · `POST /api/session/stop` · `GET /api/session/status` |
| **history** | `GET /api/history/sessions` · `GET /api/history/sessions/{id}` · `GET /api/history` (paginated, filterable) |
| **review** | `GET /api/review/queue` · `POST /api/review/applications/{id}/resolve` · `GET/PUT /api/outreach/*` · approve/discard/send/mark_sent · SMTP validate/test · send_log |
| **reports** | `GET /api/health/selectors` · `GET /api/alerts` · `GET /api/sessions/{id}/audit` · `GET /api/sessions/{id}/report[.csv]` |
| **ignored-jobs** | `GET/POST /api/ignored-jobs` · `DELETE /api/ignored-jobs/{id}` · `clear-expired` · `export.csv` |
| **ws** | `WebSocket /ws` — broadcasts live job events + 1s heartbeat |
| **system** | `POST /api/system/reset` — wipes job data, keeps config + user |
| **naukri** | `POST /api/naukri/capture-tokens` · `POST /api/naukri/test-tokens` |

**Auth:** `auth.py` issues a JWT (HS256, `sub`=user_id, 30-day expiry); `get_current_user()`
validates it on protected routes. Passwords are bcrypt-hashed (72-byte truncation).

**DB sessions:** every route takes `db = Depends(get_db)`, which yields a `SessionLocal()`
and closes it after the request. Autocommit/autoflush are off — handlers commit explicitly.

---

## 6. Live updates — the WebSocket bridge (`api/event_queue.py`)

The job loop runs in a **worker thread**, but the WebSocket lives on the **async event
loop** — so events cross a thread boundary:

1. The worker calls `tracker._emit({...})` → pushes onto a `threading.Queue` (`sync_q`, max 2000).
2. A background relay task drains `sync_q` → an `asyncio.Queue` every ~50 ms.
3. The `/ws` handler awaits the async queue and forwards each event JSON to **all**
   connected browsers; an empty tick sends a `ping` heartbeat (~1 s) to keep the socket open.

Event types include `session_started`, `job_found`, `status_change`, `apply_result`,
`backoff`, `warning`, `error`, `session_stopped`, `session_end`.

---

## 7. The heart: a session, start to finish

### 7.1 Threading & lifecycle (`api/session_manager.py`)

- `start(session_id, run_kwargs)` — sets `_is_running`, creates a `threading.Event` (stop
  signal), and submits `_run_session_sync` to a **single-worker `ThreadPoolExecutor`**. This
  keeps FastAPI responsive while Selenium blocks.
- `stop()` — sets the stop event, quits Chrome, and **immediately** marks the session row +
  any in-flight application rows as `stopped` (survives even if the worker is mid-job).
- `_on_done()` — completion callback; clears state and logs any thread exception.

### 7.2 Setup inside the worker (`_run_session_sync`)

Loads the DB `Config`, active `CVProfile`, and `Session` row → builds the in-memory
`settings.Config` → inits the tracker and audit log → decides whether to launch Chrome →
builds the LLM client → constructs a `RateLimiter` → runs each platform via
`_run_platform_db`.

**Mode → search-engine wiring (the recent fix):**

```python
run_mode = kwargs.get("mode", db_sess.mode)            # "search" | "search_and_apply"
if naukri_search_mode == "api" and run_mode != "search":
    naukri_search_mode = "selenium"   # API has NO apply endpoint → must use the browser
```

So: **search-only → Naukri API mode** (fast, no browser, no token capture);
**search & apply → Selenium** (drives the full browser flow). Chrome is only skipped when
`naukri + api + search-only`.

**Search-only threshold trick:** in `search` mode the score threshold is forced to `101`,
so nothing ever qualifies to apply — you just collect and score listings.

### 7.3 Per-job state machine (`_run_platform_db` + `api/pipeline.py`)

Every job becomes an `Application` row that walks an explicit lifecycle. Statuses live in
`core/statuses.py`:

```
 queued → fetching → scoring ─┬─▶ skipped        (low_score / ai_skip / duplicate / external-off / ignored)
                              ├─▶ applying ─┬─▶ applied
                              │             ├─▶ applied_pending_confirmation   (click ok, no banner seen)
                              │             ├─▶ saved            (external company site — link stored)
                              │             ├─▶ manual_review    (ambiguous page)
                              │             └─▶ failed           (browser error / captcha)
                              ├─▶ email_drafted → email_sent     (outreach path, send is gated)
                              └─▶ (stopped on session stop)
```

The loop applies a series of **cheap gates before any expensive work**, in order:

1. **Same-session dedupe** — skip repeated `(title, company)` within this run.
2. **Hard title gate** — `title_match.title_matches()` discards off-keyword titles *before*
   any fetch or LLM call (never even becomes a row).
3. **Daily cap** — `pipeline.daily_cap_reached()` counts persisted applies in the last 24h
   (survives restarts).
4. **Human pacing** — `rate_limiter.wait_between_jobs()` between jobs.
5. **Ignored-jobs** — `ignored_jobs.find_ignored_job()` (URL or company+title fingerprint).
6. **Persisted URL dedupe** + **per-company dedupe** (≤1 apply per company per 7 days).

Then for surviving jobs: **fetch details** → **date filter** → **classify** → **score** →
**decide** → **apply / save / draft**.

**Classification → action** (`core/job_classifier.py` + `core/page_signals.py`):

| Classification | Action |
|---|---|
| `platform_easy_apply` (LinkedIn) / `platform_internal_apply` (Naukri) | proceed to apply |
| `external_ats` | **save** the link (or skip if `include_external_review` is off) — never auto-drive a 3rd-party ATS |
| `email_outreach_candidate` | draft a recruiter email (if `outreach_mode != off`) |
| `manual_review` / `unsupported` | finalize to `manual_review` / `failed` |

**Scoring gate** (`pipeline.decide_apply`): apply **only if** the LLM recommendation is
`"apply"` **and** `score >= threshold`. An LLM "skip" is never overridden.

**Persistence & counters:** `pipeline.set_app_status()` is the single guarded transition
point — it persists the new status, writes an audit event in the same transaction, and
auto-adds stable skips to the ignore-list. Session counters are always **recomputed from
persisted rows**, so the dashboard is correct even after a crash or restart.

### 7.4 Safety & resilience

- **Rate limiting** — `utils/rate_limiter.py`: per-hour/day caps + randomized waits
  (between-jobs, after-apply); raises `RateLimitExceededError` → session stops cleanly.
- **Backoff** — after `MAX_CONSECUTIVE_FAILURES` (3), exponential sleep (90 s → capped at
  600 s), interruptible by the stop event. CAPTCHA/challenge pages **always abort** the
  platform loop — no bypass, ever.
- **Evidence** — on failure, `core/evidence.py` saves a screenshot + page-text excerpt to
  `data/evidence/app_<id>/` for offline diagnosis.
- **Audit** — `core/audit.py` appends every meaningful decision to `audit_events`.

---

## 8. Platform automation (`platforms/`)

### 8.1 The contract (`base_platform.py`)

Every platform implements: `check_login()`, `login()`, `search_jobs()`,
`get_job_description()`, `apply_to_job()`, plus overridable `get_job_details()` and
`collect_page_signals()`. Shared dataclasses: **`JobListing`** (search hit; carries
`raw_data` for API mode), **`JobDetails`** (enriched JD), **`ApplicationResult`**
(status + failure_reason + external_url).

### 8.2 Naukri — dual mode

`naukri/platform.py` routes by `naukri_search_mode`:

- **Selenium mode** (used for **search & apply**):
  - `login.py` — real username/password login at `nlogin/login`, with logged-in/out marker
    detection and session-clearing.
  - `search.py` — builds SEO search URLs, waits for React `[data-job-id]` cards, parses each
    via JS (avoids stale-element errors), paginates, dedupes by URL.
  - `job_scraper.py` — opens the JD page; extracts description, skills, salary, experience,
    posted date, openings, applicants, "about company", company logo.
  - `apply.py` — the apply engine:
    - Detects **"Apply on company site"** → captures the external URL (from button attrs, or
      a real click → new tab) and returns `saved` — **never auto-drives third-party ATS**.
    - Otherwise clicks Naukri's internal apply → drives the **chatbot drawer** for up to 25
      turns: reads each bot question, gets an answer from the **LLM**
      (`answer_chatbot_question`) or a **rule-based fallback** (prefer "yes", experience from
      CV, "30 days" notice, "as per industry standards" salary), fills radio/text inputs,
      clicks save. Then handles a confirmation modal and verifies success via selector
      fallbacks → text markers → `applied_pending_confirmation` if nothing bad appeared.

- **API mode** (used for **search-only**):
  - `api_search.py` — hits `naukri.com/jobapi/v3/search`. This endpoint is **reCAPTCHA
    Enterprise-gated**: a plain HTTP client gets `406 recaptcha required`. The workaround is
    to replay a logged-in browser's **`cookie` + `nkparam`** headers (`build_session`). The
    API response is rich — `get_job_details_api()` parses skills, salary, experience,
    AmbitionBox rating/reviews, IST posted date, openings — with **zero extra requests**
    (the full record rides along on `JobListing.raw_data`). Raises `NaukriRecaptchaError` on
    406 (tokens expired).
  - **Why API mode can't apply:** there is no apply endpoint — applying needs a live browser
    session (chatbot, modals, per-job cookies). `apply_to_job()` raises in API mode. This is
    exactly why search & apply forces Selenium (§7.2).
  - `token_capture.py` — auto-harvests fresh `cookie`/`nkparam` by launching a real Chrome
    (with CDP performance logging), navigating to a search page, and lifting the headers off
    the search XHR. _Known issue (2026-06-30): this second-Chrome launch can crash
    (`session not created`) — likely a chromedriver/Chrome version or profile-lock problem;
    not yet root-caused._

### 8.3 LinkedIn — Selenium only

`linkedin/platform.py` has no API mode. `login.py` is a **stub** (assumes you're already
logged in). `search.py` builds search URLs with the Easy-Apply filter (`f_LF=f_AL`) and
date filter (`f_TPR`), paginating 25/page. `apply.py` drives the **Easy Apply modal** —
generic form-fill (phone, experience, selects) across up to 10 Next/Review/Submit steps. No
chatbot; pure form navigation.

### 8.4 Chrome control (`core/chrome_manager.py`)

Three driver modes for three needs:

| Function | Purpose |
|---|---|
| `ensure_chrome_running(port, dir)` | Launch (if needed) + attach to a **persistent debug-port** Chrome, reused across the whole job loop |
| `get_driver(port)` | Lightweight Selenium attach to an already-running debug Chrome |
| `get_capture_driver(dir)` | **Fresh** Chrome with CDP performance logging enabled — used only by token capture (perf logging is unreliable on an attached debug Chrome) |

All disable the automation flag, password manager, and notifications.

### 8.5 Selectors & health (`core/selectors.py`, `core/selector_health.py`)

All CSS selectors live in one registry as **ordered fallback lists**
(`SELECTORS[platform][purpose]`). `find_first()` / `find_first_clickable()` try each in
turn and log which matched (so drift is visible). `selector_health.py` validates every
fallback group against **DOM snapshot fixtures** in `tests/fixtures/` and counts live
failure incidents from the DB — surfaced via `GET /api/health/selectors` and `/api/alerts`.

---

## 9. AI / scoring (`core/`)

- **Provider abstraction** (`llm_provider.py`): one `ai_provider` setting picks among
  **azure** (default), **openai**, **gemini**, **groq**, **openrouter**, or **fuzzy**
  (no-AI). All real providers go through the OpenAI-compatible client by swapping
  `base_url`. `validate_llm_settings()` enforces required keys before a run.
- **LLM client** (`llm_client.py`): builds a CV-aware system prompt, then exposes
  `score_job()` (→ `JobScore`: 0–100 score, apply/skip recommendation, rationale, matched &
  missing skills), `answer_chatbot_question()`, and `draft_outreach_email()`. Retries with
  backoff on rate limits; degrades gracefully on parse errors.
- **Fuzzy fallback** (`fuzzy_client.py`): a drop-in replacement that scores via `difflib`
  skill/title overlap — used when `ai_provider="fuzzy"`, no API key needed.
- **CV parsing** (`cv_parser.py`): `pdfplumber` extracts text; an LLM (or a regex/lexicon
  fuzzy path) fills `CVData` (name, skills, titles, years, education, summary).
- **Outreach** (`outreach.py`): composes a recruiter email (LLM or template). Sending is
  **triple-gated** — requires `outreach_mode == send_after_approval`, a draft in `approved`
  status, **and** valid SMTP. Nothing is ever sent automatically.
- **Email discovery** (`email_discovery.py`): extracts recruiter emails **only from visible
  public job HTML** (strips scripts/hidden nodes; filters noreply/vendor addresses).

---

## 10. Tests (`tests/`)

`pytest` suite focused on safety and correctness, validated against real DOM fixtures
(`tests/fixtures/*.html`):

| Test | Guards |
|---|---|
| `test_status_transitions.py` | lifecycle states are explicit & guarded; no row stuck "in-flight"; apply gated on LLM recommendation |
| `test_stop_session.py` | stop immediately persists `stopped` everywhere |
| `test_safety_limits.py` | daily cap, per-company dedupe, pacing, capped backoff |
| `test_easy_apply_filtering.py` | LinkedIn uses the platform filter; non-easy-apply never auto-applies |
| `test_selector_health.py` | fallback selectors match fixtures; failures route to manual review |
| `test_naukri_fixtures.py` | internal/external/no-button/login-required/recruiter-email pages |
| `test_outreach_drafts.py` / `test_smtp_and_send_log.py` | drafts never auto-send; send requires approval; immutable send log |
| `test_email_discovery.py` | only visible content is scraped |
| `test_title_targeting.py` | only keyword-matching titles get scored |
| `test_ignored_jobs.py` | ignore fingerprinting + expiry |
| `test_audit_and_evidence.py` | audit log + failure evidence |
| `test_export_report.py` | exact CSV schema |

---

## 11. Glossary of key files

| If you want to… | Look at |
|---|---|
| Add/Change an API endpoint | `api/routes/*.py` (+ `api/schemas.py`) |
| Change a DB field | `api/models.py` (+ the migration block in `api/database.py`) |
| Change how a session runs | `api/session_manager.py` (orchestration) + `api/pipeline.py` (state) |
| Tune the apply/skip decision | `api/pipeline.py::decide_apply` + `core/llm_client.py` prompts |
| Fix a broken site selector | `core/selectors.py` (+ run `selector_health`) |
| Change Naukri apply behavior | `platforms/naukri/apply.py` |
| Change Naukri search (API) | `platforms/naukri/api_search.py` (+ `token_capture.py`) |
| Add an LLM provider | `core/llm_provider.py` |
| Adjust safety/pacing | `utils/rate_limiter.py` + constants in `session_manager.py` |
```
