import type { Page, Route } from "@playwright/test";

/* ──────────────────────────────────────────────────────────────────────────
   API mocking + request recording.

   Every test runs against a fully mocked backend: no real credentials,
   SMTP, LLM, CV parsing, or live job portals are ever contacted.
   ────────────────────────────────────────────────────────────────────────── */

export interface RecordedCall {
  method: string;
  path: string;        // pathname + search
  body: any;           // parsed JSON body (or raw string)
}

export interface ResponseSpec {
  status?: number;
  json?: unknown;
  body?: string;
  contentType?: string;
  delayMs?: number;
  /** abort the request to simulate an offline backend */
  abort?: boolean;
}

export type Overrides = Record<string, ResponseSpec | ((route: Route) => Promise<void> | void)>;

export interface Recorder {
  all: RecordedCall[];
  calls(pathPrefix: string, method?: string): RecordedCall[];
  count(pathPrefix: string, method?: string): number;
}

/* ── Default dataset (mirrors backend schemas) ───────────────────────────── */

export const CV_PROFILE = {
  id: 1, name: "Sumit Tiwari", email: "sumit@example-candidate.dev",
  phone: "+91 9999999999",
  skills: ["Selenium", "Python", "FastAPI", "Playwright", "SQL"],
  job_titles: ["QA Engineer", "SDET"],
  experience_years: 4, education: ["B.Tech"], summary: "QA automation engineer.",
  pdf_path: "/cv/resume.pdf", created_at: "2026-06-01T10:00:00Z", is_active: true,
};

export const CONFIG = {
  naukri_email: "user@naukri.test", naukri_password: "***",
  linkedin_email: "", linkedin_password: "",
  azure_openai_endpoint: "", azure_openai_api_key: "",
  azure_deployment_name: "gpt-4o-mini",
  ai_provider: "groq",
  openai_api_key: "", openai_model: "gpt-4o-mini",
  gemini_api_key: "", gemini_model: "gemini-2.5-flash",
  groq_api_key: "***", groq_model: "openai/gpt-oss-120b",
  openrouter_api_key: "", openrouter_model: "openai/gpt-oss-120b",
  openrouter_base_url: "https://openrouter.ai/api/v1",
  confidence_threshold: 75, port_num: 9222,
  max_jobs_per_hour: 30, max_jobs_per_day: 150,
  easy_apply_only: true, include_external_review: true,
  outreach_mode: "draft_only",
  smtp_host: "", smtp_port: 587, smtp_username: "", smtp_password: "", smtp_from: "",
  is_configured: true,
};

function app(id: number, over: Record<string, unknown> = {}) {
  return {
    id, session_id: 1, platform: "naukri",
    job_title: `Job ${id}`, company: `Company ${id}`,
    job_url: `https://www.naukri.test/job-${id}`,
    score: 0, location: "Gurugram", experience_required: "", salary: "",
    key_skills: [], matched_skills: [], missing_skills: [],
    external_site_url: "", status: "queued", classification: "",
    failure_reason: "", recommendation: "", rationale: "",
    job_description: "", error_message: null,
    timestamp: "2026-06-11T10:00:00Z", updated_at: null,
    ...over,
  };
}

export const APPS = [
  app(1, { job_title: "Senior QA Engineer", company: "TechCorp", status: "applied",
           score: 88, recommendation: "apply", rationale: "Strong overlap.",
           classification: "platform_internal_apply",
           matched_skills: ["Selenium", "Python"], missing_skills: ["Rust"],
           experience_required: "3-6 Yrs", salary: "12-18 LPA" }),
  app(2, { job_title: "SDET II", company: "CloudNine", status: "applied_pending_confirmation",
           score: 81, recommendation: "apply", classification: "platform_easy_apply" }),
  app(3, { job_title: "QA Automation Lead", company: "MegaCorp", status: "saved",
           score: 79, recommendation: "apply", classification: "external_ats",
           failure_reason: "external_site", rationale: "Good fit, external site.",
           external_site_url: "https://careers.megacorp.test/jobs/77" }),
  app(4, { job_title: "Sales Executive", company: "SellMore", status: "skipped",
           failure_reason: "title_mismatch" }),  // never scored → score —
  app(5, { job_title: "Test Engineer", company: "DataCo", status: "skipped",
           score: 58, recommendation: "skip", failure_reason: "low_score",
           rationale: "Domain mismatch." }),
  app(6, { job_title: "QA Engineer (Contract)", company: "StartupXYZ", status: "email_drafted",
           score: 84, recommendation: "apply", classification: "email_outreach_candidate" }),
  app(7, { job_title: "Automation Engineer", company: "FinServe", status: "failed",
           score: 77, recommendation: "apply", failure_reason: "confirmation_missing",
           error_message: "Platform showed an error after the apply click" }),
];

export const DRAFT = {
  id: 11, application_id: 6, session_id: 1,
  recruiter_email: "priya@startupxyz.test",
  email_source: "mailto", email_source_url: "https://www.naukri.test/job-6",
  subject: "Application for QA Engineer (Contract) — Sumit Tiwari",
  body: "Dear Hiring Team,\n\nI would love to be considered.\n\nBest,\nSumit",
  status: "draft", created_at: "2026-06-11T10:00:00Z", updated_at: null, sent_at: null,
  job_title: "QA Engineer (Contract)", company: "StartupXYZ",
  job_url: "https://www.naukri.test/job-6",
};

export const SESSION = {
  id: 1, platform: "naukri", mode: "search_and_apply", location: "gurugram",
  job_target: 5, confidence_threshold: 75, keywords: ["QA Engineer"],
  easy_apply_only: true, include_external_review: true, outreach_mode: "draft_only",
  started_at: "2026-06-11T10:00:00Z", ended_at: "2026-06-11T11:00:00Z",
  applied: 2, skipped: 2, errors: 1, status: "completed",
};

export const STATUS_COUNTS = {
  queued: 0, fetching: 0, scoring: 0, applying: 0,
  applied: 1, applied_pending_confirmation: 1, skipped: 2, saved: 1,
  manual_review: 0, email_drafted: 1, email_sent: 0, failed: 1, stopped: 0,
  total: 7,
};

export const CSV_HEADER =
  "timestamp,platform,company,company_logo_url,job_title,location," +
  "experience_required,salary,confidence,job_status,posted_date,openings," +
  "applicants_count,key_skills,matched_skills,missing_skills," +
  "external_site_url,about_company,job_description,job_url";

export const CSV_BODY =
  `${CSV_HEADER}\n2026-06-11 10:00:00,naukri,TechCorp,,Senior QA Engineer,Gurugram,3-6 Yrs,12-18 LPA,88,applied,,,,"Selenium, Python",Selenium,Rust,,,,https://www.naukri.test/job-1\n`;

/* ── Default route table ─────────────────────────────────────────────────── */

function defaults(): Record<string, ResponseSpec> {
  return {
    "GET /api/health": { json: { status: "ok" } },
    "GET /api/config": { json: CONFIG },
    "PUT /api/config": { json: { status: "saved", is_configured: true } },
    "POST /api/config/test": {
      json: { ok: true, provider: "groq", model: "openai/gpt-oss-120b", output: "connection ok" },
    },
    "GET /api/cv/profile": { json: CV_PROFILE },
    "POST /api/cv/parse": { json: CV_PROFILE },
    "GET /api/session/status": {
      json: { is_running: false, session_id: null, started_at: null,
              counts: STATUS_COUNTS, session: SESSION },
    },
    "POST /api/session/start": { json: { status: "started", session_id: 2 } },
    "POST /api/session/stop": { json: { status: "stopped" } },
    "GET /api/review/queue": {
      json: { manual_review: [], drafts: [DRAFT],
              skipped: [APPS[3], APPS[4]], saved: [APPS[2]] },
    },
    "POST /api/review/applications/3/resolve": { json: { status: "applied" } },
    "POST /api/outreach/11/approve": { json: { ...DRAFT, status: "approved" } },
    "POST /api/outreach/11/discard": { json: { ...DRAFT, status: "discarded" } },
    "POST /api/outreach/11/mark_sent": { json: { ...DRAFT, status: "sent" } },
    "POST /api/outreach/11/send": { json: { ...DRAFT, status: "sent" } },
    "PUT /api/outreach/11": { json: DRAFT },
    "POST /api/outreach/smtp/test": { json: { ok: true, sent_to: "me@mailbox.test" } },
    "GET /api/outreach/smtp/validate": { json: { ok: false, problems: ["SMTP host is empty."] } },
    "GET /api/alerts": { json: { alerts: [] } },
    "GET /api/history/sessions": { json: [SESSION] },
    "GET /api/history": {
      json: { total: APPS.length, page: 1, per_page: 20, records: APPS },
    },
    "GET /api/sessions/1/report.csv": { body: CSV_BODY, contentType: "text/csv" },
    "GET /api/sessions/1/report": { json: { session: SESSION, totals: {}, applications: [] } },
    "GET /api/sessions/1/audit": { json: [] },
  };
}

/* ── Route interception ──────────────────────────────────────────────────── */

export async function setupMocks(page: Page, overrides: Overrides = {}): Promise<Recorder> {
  const all: RecordedCall[] = [];
  const table = defaults();

  // NOTE: must anchor on the path start — a "**/api/**" glob would also
  // intercept Vite's own /src/api/*.ts module requests.
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname + url.search;
    const method = req.method();

    let body: any = undefined;
    const post = req.postData();
    if (post) {
      try { body = JSON.parse(post); } catch { body = post; }
    }
    all.push({ method, path, body });

    const keyExact = `${method} ${url.pathname}`;
    const override = overrides[keyExact] ?? findPrefix(overrides, method, url.pathname);
    const spec = override ?? table[keyExact] ?? findPrefix(table, method, url.pathname);

    if (!spec) {
      await route.fulfill({ status: 404, contentType: "application/json",
                            body: JSON.stringify({ detail: `no mock for ${keyExact}` }) });
      return;
    }
    if (typeof spec === "function") {
      await spec(route);
      return;
    }
    if (spec.abort) {
      await route.abort("connectionrefused");
      return;
    }
    if (spec.delayMs) {
      await new Promise((r) => setTimeout(r, spec.delayMs));
    }
    await route.fulfill({
      status: spec.status ?? 200,
      contentType: spec.contentType ?? "application/json",
      body: spec.body ?? JSON.stringify(spec.json ?? {}),
    });
  });

  return {
    all,
    calls: (prefix, method) => all.filter(
      (c) => c.path.startsWith(prefix) && (!method || c.method === method)),
    count: (prefix, method) => all.filter(
      (c) => c.path.startsWith(prefix) && (!method || c.method === method)).length,
  };
}

function findPrefix<T>(map: Record<string, T>, method: string, pathname: string): T | undefined {
  for (const key of Object.keys(map)) {
    const [m, p] = key.split(" ");
    if (m === method && p.endsWith("*") && pathname.startsWith(p.slice(0, -1))) {
      return map[key];
    }
  }
  return undefined;
}

/** Simulate a backend that is completely down. */
export async function offlineBackend(page: Page): Promise<void> {
  await page.route((url) => url.pathname.startsWith("/api/"),
                   (route) => route.abort("connectionrefused"));
}
