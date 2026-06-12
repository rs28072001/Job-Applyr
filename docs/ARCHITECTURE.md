# Job-Applyr — Complete Workflow, Architecture & Infrastructure Document

> Local, single-user job application assistant for Naukri and LinkedIn.
> Everything — credentials, AI keys, resume, database, browser — stays on your machine.

---

## 1. High-level overview

### 1.1 What the product does

Job-Applyr automates the repetitive part of job hunting while keeping every risky or
irreversible decision with the user:

| Job type | What happens | User effort |
|---|---|---|
| LinkedIn **Easy Apply** | Applied **automatically** (platform Easy Apply filter + modal flow) | none |
| Naukri **internal apply / chatbot** | Applied **automatically** (chatbot answered by AI) | none |
| **External company-site** job | **Saved automatically** with its link — never auto-driven | apply later if interested |
| External job with a **visible recruiter email** | Outreach email **drafted** (never sent) | approve / copy / discard |
| Unreadable page (no apply button, odd layout) | Marked **Needs Attention** with a reason | optional look |
| Everything else | **Skipped** with an explicit reason | none |

The session **never waits for the user**. Saved/attention/draft items are informational.

### 1.2 Automatic-apply rules (all must be true)

1. Job is **supported** (platform-native apply flow detected).
2. Job **title matches** the user's target keywords (synonym-aware matcher).
3. **LLM recommendation** is `apply`.
4. **Confidence score** ≥ user threshold (default 75).
5. **Daily cap** not reached (persisted count, survives restarts).
6. **Company not already contacted** in the last 7 days.

If any rule fails the job is finalized with a precise reason (`low_score`, `ai_skip`,
`title_mismatch`, `duplicate_company`, `external_site`, `unsupported`, …) and the loop
moves on immediately.

### 1.3 Account-safety principles (hard rules)

- **No CAPTCHA bypass, no proxies, no stealth/fingerprint tricks** — ever.
- Challenge/login pages → exponential backoff (90 s → 10 min cap) and platform abort.
- Human-paced randomized delays: 4–9 s between jobs, 3–6 s after an apply.
- Hourly + daily caps; URL, title+company, and per-company dedupe.
- Recruiter emails come **only from visible public page content** (job description,
  recruiter cards, visible `mailto:` links). Hidden/script/comment content is discarded.
- Emails are **never sent automatically**: `draft_only` is the default; sending requires
  `send_after_approval` mode **and** per-draft human approval **and** the user's own SMTP.

---

## 2. System architecture

### 2.1 Component diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                            User's machine                              │
│                                                                        │
│  ┌─────────────┐   HTTP /api/*  ┌──────────────────────────────────┐  │
│  │  React SPA  │◄──────────────►│        FastAPI backend           │  │
│  │ (Vite 5173) │   WS /ws       │           (port 8001)            │  │
│  └─────────────┘                │                                  │  │
│   Dashboard ·                   │  ┌─────────┐  ┌───────────────┐  │  │
│   Setup wizard ·                │  │ Routes  │  │ SessionManager│  │  │
│   Saved & Skipped ·             │  │ (REST)  │  │ (worker thread│  │  │
│   History                       │  └────┬────┘  │  + stop event)│  │  │
│                                 │       │       └──────┬────────┘  │  │
│                                 │  ┌────▼──────────────▼────────┐  │  │
│                                 │  │       Pipeline (DB-backed) │  │  │
│                                 │  │ classify → score → decide  │  │  │
│                                 │  └────┬───────────┬───────────┘  │  │
│                                 │       │           │              │  │
│                       ┌─────────┴──┐ ┌──▼────┐ ┌────▼───────────┐  │  │
│                       │  SQLite DB │ │  LLM  │ │ Platform layer │  │  │
│                       │ (sessions, │ │client │ │ Naukri/LinkedIn│  │  │
│                       │ jobs, audit│ │(user's│ │   (Selenium)   │  │  │
│                       │ drafts,log)│ │ key)  │ └────┬───────────┘  │  │
│                       └────────────┘ └───────┘      │              │  │
│                                                ┌────▼───────────┐  │  │
│                                                │ Chrome (CDP    │  │  │
│                                                │ attach, local  │  │  │
│                                                │ profile)       │  │  │
└────────────────────────────────────────────────┴────────────────┴──┴──┘
        External: job portals (via the user's own logged-in Chrome),
        the user's chosen LLM API, optionally the user's own SMTP server.
```

### 2.2 Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS (light/dark/system), Zustand, react-router |
| Backend | Python 3.10+, FastAPI, SQLAlchemy 2, Uvicorn |
| Automation | Selenium attached to the user's real Chrome via CDP (port 9222) |
| AI | OpenAI-compatible client — Groq / OpenAI / Gemini / OpenRouter (user's own key) |
| Storage | Single SQLite file `backend/data/smart_job_assistant.db` (auto-migrating) |
| Realtime | WebSocket `/ws` event stream (tracker → event queue → relay) |
| Tests | pytest (106 backend tests) + Playwright (83 E2E tests, fully mocked APIs) |

### 2.3 Infrastructure / deployment

Everything runs locally — there is **no server-side infrastructure**:

```
./run.sh
  ├─ creates/activates backend/venv, installs requirements
  ├─ init_db(): creates tables + applies additive column/status migrations
  ├─ uvicorn api.server:app  → http://localhost:8001  (REST + WS + docs at /docs)
  └─ npm run dev             → http://localhost:5173  (proxies /api and /ws to 8001)
```

Chrome is launched/attached with a dedicated local profile under
`backend/data/chrome_profiles/<hash-of-account>` so portal logins persist between runs.
Evidence captures go to `backend/data/evidence/app_<id>/`, logs to `backend/logs/`.

---

## 3. End-to-end workflow (what happens when you press "Launch session")

```
Setup wizard (3 steps)
  1) Resume upload  → POST /api/cv/parse → LLM extracts skills/titles → stored locally
  2) Preferences    → platform, keywords, location, target, min score,
                      Easy Apply only (default ON), save-external-jobs (default ON)
  3) Credentials    → portal logins, AI provider+key, outreach mode (+SMTP), Launch
       └─ PUT /api/config  → POST /api/session/start

SessionManager (background worker thread)
  ├─ audit: session_started
  ├─ attach Chrome → login check (LoginError → session ends gracefully)
  ├─ search (LinkedIn adds f_LF=f_AL Easy Apply filter when enabled)
  └─ FOR EACH listing:                                   status written at every step
       0  daily cap reached? ──────────────► stop platform loop
       1  duplicate URL / title+company / company-in-7-days? ► skip (reason recorded)
       2  title_matches(keywords)? ────────► no: SKIPPED  (title_mismatch)
       3  create row  ························ QUEUED
       4  fetch job details ·················· FETCHING
       5  read page signals → classify:
            platform_easy_apply / platform_internal_apply → continue
            external_ats              → SAVED  (external_site) — link captured
            email_outreach_candidate  → continue (outreach path)
            manual_review             → MANUAL_REVIEW (apply_button_not_found)
            unsupported               → FAILED (login_required / captcha_or_challenge)
       6  LLM score ·························· SCORING   (score, rationale, matched/missing)
       7  decide: recommendation==apply AND score≥threshold?
            no  → SKIPPED (low_score | ai_skip)
            yes + outreach path → draft stored → EMAIL_DRAFTED (never sent)
            yes + platform path → APPLYING
       8  platform apply (Easy Apply modal / Naukri chatbot via LLM answers)
            confirmation banner/text  → APPLIED
            click ok, nothing bad     → APPLIED_PENDING_CONFIRMATION
            login/captcha/error       → FAILED (+ evidence capture + backoff/abort)
       9  human pause (4–9 s) → next job

Finalize: every in-flight row forced to a terminal state (nothing ever stuck),
          counters recomputed from persisted rows, audit: session_finalized.

Stop button: signals the worker, closes Chrome, IMMEDIATELY persists `stopped`
on the session and every active row — optimistic UI update in the same click.
```

---

## 4. Low-level design

### 4.1 Job lifecycle state machine (`backend/core/statuses.py`)

```
queued → fetching → scoring → applying → applied
   │        │          │         ├────→ applied_pending_confirmation → (applied)
   │        │          ├──→ email_drafted → email_sent
   │        │          │
   └────────┴──────────┴──→ skipped | saved | manual_review | failed | stopped

saved / manual_review → applied | skipped   (user "I applied" / "Remove")
Terminal: applied, applied_pending_confirmation, skipped, failed, stopped, email_sent
```

Transitions are **guarded** (`can_transition`): a terminal row can never regress,
`set_app_status` refuses invalid moves, and every change writes an `audit_events` row
in the same transaction plus a WebSocket `job_status` event.

**Failure reasons** (stored on the row, shown in UI/CSV):
`login_required, apply_button_not_found, external_site, captcha_or_challenge,
confirmation_missing, unsupported_flow, low_score, ai_skip, title_mismatch,
duplicate_company, already_applied, daily_cap_reached, rate_limited, scoring_failed,
browser_error, session_stopped`.

### 4.2 Classification (`core/page_signals.py` + `core/job_classifier.py`)

`signals_from_html()` parses `driver.page_source` (the same parser runs against static
test fixtures): internal/external apply buttons, Easy Apply markers, login phrases,
challenge phrases, already-applied markers, and **visible** emails.
`classify_job()` maps signals → one of six classifications; `route_classification()`
maps classification + settings → pipeline action. Pure functions, fully unit-tested.

### 4.3 Selector resilience (`core/selectors.py` + `core/selector_health.py`)

All CSS selectors live in one registry as **ordered fallback lists** (joined as CSS
`a, b, c` unions in live code). A health check validates every group against 15 bundled
DOM snapshot fixtures (`backend/tests/fixtures/*.html`) and counts live selector
incidents from the last 24 h of rows — surfaced at `GET /api/health/selectors` and as
dashboard alerts. A missing apply button never fails silently: the job goes to
Needs Attention with reason `apply_button_not_found`.

### 4.4 Safety limits (`api/pipeline.py`, `utils/rate_limiter.py`, `api/session_manager.py`)

- `daily_cap_reached()` — counts `applied` + `applied_pending_confirmation` rows in the
  last 24 h from the DB (restart-proof) against `max_jobs_per_day`.
- `is_duplicate_company()` — 7-day window, case-insensitive, counts email contact too.
- `RateLimiter` — randomized waits; `wait_between_jobs` 4–9 s; hourly/daily action caps.
- `_backoff_seconds(n)` — 90 s · 2ⁿ⁻¹ capped at 600 s on challenge/login/repeat failures,
  then the platform loop **aborts** (interruptible by Stop).

### 4.5 Title targeting (`core/title_match.py`)

Tokenizes keyword and title; ignores generic tokens (senior, lead, remote, …); requires
≥ half of a keyword's significant tokens to appear (prefix + synonym tolerance:
qa↔tester/sdet, developer↔engineer, frontend↔ui, …). No keywords → no filter.

### 4.6 Email outreach (`core/email_discovery.py`, `core/outreach.py`)

Discovery strips `<script>/<style>/<noscript>`, comments, and `display:none/hidden`
regions, then extracts visible `mailto:` links (preferred) and plain-text addresses,
filtering junk (noreply, example.com, platform domains, image names). Drafts are
LLM-written with a template fallback, stored with `recruiter_email`, `email_source`,
`email_source_url`, and status `draft`. Sending is a single gated path:
mode `send_after_approval` + draft `approved` + user SMTP — anything else raises.
Every send (SMTP or "I sent it") writes an immutable `outreach_send_log` row
(job, company, recipient, subject, method, timestamp).

### 4.7 Observability

- **Audit log** — `audit_events` table: session_started, every status_change, login,
  backoff, daily_cap_reached, session_stopped/finalized, outreach_sent.
  `GET /api/sessions/{id}/audit`.
- **Evidence capture** — on real failures only: screenshot + visible-text excerpt under
  `data/evidence/app_<id>/`, path stored on the row.
- **Run report** — `GET /api/sessions/{id}/report` (JSON) and `…/report.csv`
  (exact 20-column schema: timestamp, platform, company, company_logo_url, job_title,
  location, experience_required, salary, confidence, job_status, posted_date, openings,
  applicants_count, key_skills, matched_skills, missing_skills, external_site_url,
  about_company, job_description, job_url — empty strings for missing values).
- **Alerts** — `GET /api/alerts`: broken selectors, selector-incident spikes,
  missing SMTP in send mode, >30 % failure rate in the last session.

### 4.8 Data model (SQLite, auto-migrating in `api/database.py`)

| Table | Purpose / key columns |
|---|---|
| `config` (singleton) | credentials, AI provider/keys, thresholds, caps, `easy_apply_only`, `include_external_review`, `outreach_mode`, SMTP — **stored locally only** |
| `cv_profiles` | parsed resume (name, skills, titles, experience, raw text) |
| `sessions` | one run: platform, mode, keywords, toggles, counters (recomputed from rows), status |
| `applications` | one job: full details, `score`, `recommendation`, `rationale`, `status`, `classification`, `failure_reason`, `external_site_url`, `evidence_path` |
| `outreach_drafts` | draft/approved/sent/discarded + email source URL |
| `outreach_send_log` | immutable send audit trail |
| `audit_events` | append-only session audit log (JSON detail) |
| `users` | local auth shim (no login required for local use) |

Migrations are additive `ALTER TABLE`s plus data lifts run at startup
(e.g. legacy `error`→`failed`, `skipped_external`→`saved`, reason renames,
external rows → `saved`). Existing databases upgrade automatically on launch.

### 4.9 API surface (FastAPI, all under `/api`)

```
config:    GET/PUT /config · POST /config/test
cv:        POST /cv/parse · GET/PUT /cv/profile
session:   POST /session/start · POST /session/stop (idempotent) · GET /session/status
history:   GET /history (filters+pagination) · GET /history/sessions[/id]
review:    GET /review/queue (saved + needs-attention + skipped + drafts)
           POST /review/applications/{id}/resolve  (mark_applied | dismiss)
outreach:  GET /outreach · PUT /outreach/{id} · POST /outreach/{id}/approve|discard|
           send|mark_sent · GET/POST /outreach/smtp/validate|test · GET /outreach/send_log
reports:   GET /sessions/{id}/report[.csv] · GET /sessions/{id}/audit
health:    GET /health · GET /health/selectors · GET /alerts
ws:        /ws — live events (job_status, job_classified, llm_score, outreach_drafted,
           backoff, session_end, session_stopped, …)
```

### 4.10 Frontend structure (`frontend/src`)

```
api/client.ts,types.ts     axios instance + typed mirrors of backend schemas
store/sessionStore.ts      Zustand store fed by WS events (jobs keyed by row id)
theme.ts + ThemeToggle     light/dark/system, persisted, pre-paint applied
components/ui.tsx          Card, StatusBadge (13 states), reasons, empty/loading states
components/JobDetailDrawer per-job drawer (status, score, rationale, skills, links)
pages/SetupPage            3-step wizard (resume → preferences → credentials/launch)
pages/DashboardPage        command center: counters from persisted rows, alerts,
                           live timeline, job table (WS + DB hydration), export
pages/ReviewQueuePage      Saved & Skipped: saved external jobs, needs-attention,
                           recent skips with reasons, email drafts
pages/HistoryPage          sessions list, filterable applications, CSV export
```

Counters always come from **persisted rows** (4 s polling of `/api/session/status`),
so a page refresh never loses state; WebSocket events provide the live feel.

---

## 5. Testing strategy

| Suite | Count | Covers |
|---|---|---|
| Backend pytest (`backend/tests`) | **106** | classification & routing per fixture, Easy Apply filtering, title targeting, status transitions / no-stuck-rows, stop semantics, daily cap & company dedupe & backoff math, email-discovery visibility rules, drafts-never-sent (SMTP spy), SMTP validation & send log, audit & evidence, CSV schema, selector health |
| Playwright E2E (`frontend/e2e`) | **83** | every button/link/row on every page, request method+URL+payload assertions via a fully mocked API, downloads, clipboard, dark theme persistence, offline/500/slow-API resilience, duplicate-click protection, reload persistence |

Run: `cd backend && pytest` · `cd frontend && npm run test:e2e` (mocked — no real
portals/SMTP/LLM ever contacted; screenshots/videos/traces kept on failure).

---

## 6. Known limitations & remaining risks

1. **Selector drift** — portals redesign; the health check + alerts detect it and jobs
   degrade to Needs Attention rather than mis-clicking, but apply success depends on
   keeping `core/selectors.py` fixtures roughly current.
2. **`applied_pending_confirmation`** rows are almost certainly applied (click ok, no
   error/login/challenge) but worth an occasional spot-check on the portal.
3. **ToS** — automated applying violates LinkedIn/Naukri terms. Caps, pacing, backoff
   and Easy-Apply-only reduce account risk; they cannot eliminate it. No protection
   bypass is implemented by design.
4. **LLM quality** — scores/recommendations are only as good as the configured model;
   `ai_skip` decisions are conservative (skip is always honoured).
5. **Synonym list** in the title matcher is tuned for software roles; extend
   `core/title_match.py::_SYNONYMS` for other domains.
6. Live-portal flows (real login walls, real chatbot variants) can only be validated
   with a supervised dry run — automated tests use DOM snapshots and mocks.
```
