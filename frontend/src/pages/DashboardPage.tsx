import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Square, ExternalLink, CheckCircle2, XCircle, AlertCircle, AlertTriangle,
  Inbox, Activity, ListChecks, Mail, Loader2, Search, OctagonX, Download, Play,
} from "lucide-react";
import { api } from "../api/client";
import { useWebSocket } from "../hooks/useWebSocket";
import { useSessionStore, type JobEntry } from "../store/sessionStore";
import type {
  ApplicationRecord, PaginatedApplications, ReviewQueueResponse, SessionStatusResponse, AppConfig,
} from "../api/types";
import {
  Card, CardHeader, ClassificationBadge, EmptyState, ScorePill, StatusBadge, failureLabel,
} from "../components/ui";
import JobDetailDrawer from "../components/JobDetailDrawer";

/* ── Summary cards ───────────────────────────────────────────────────────── */

function SummaryCard({ label, value, sub, icon: Icon, tone }: {
  label: string; value: number | string; sub?: string; icon: React.ElementType; tone: string;
}) {
  return (
    <Card className="px-4 py-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">{label}</p>
        <Icon className={`w-3.5 h-3.5 ${tone}`} />
      </div>
      <p className="text-2xl font-bold text-slate-900 mt-1 leading-none">{value}</p>
      {sub && <p className="text-[11px] text-slate-400 mt-1">{sub}</p>}
    </Card>
  );
}

/* ── Session state banner ────────────────────────────────────────────────── */

function SessionBanner() {
  const uiState = useSessionStore((s) => s.uiState);
  const map = {
    idle:      null,
    running:   { cls: "bg-emerald-50 border-emerald-200 text-emerald-700", dot: "bg-emerald-500 animate-pulse", label: "Running" },
    completed: { cls: "bg-slate-50 border-slate-200 text-slate-600", dot: "bg-slate-400", label: "Completed" },
    stopped:   { cls: "bg-orange-50 border-orange-200 text-orange-700", dot: "bg-orange-500", label: "Stopped" },
    failed:    { cls: "bg-red-50 border-red-200 text-red-700", dot: "bg-red-500", label: "Failed" },
  } as const;
  const meta = map[uiState];
  if (!meta) return null;
  return (
    <span className={`inline-flex items-center gap-1.5 border text-xs font-semibold px-2 py-0.5 rounded ${meta.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

/* ── Job row ─────────────────────────────────────────────────────────────── */

function JobRow({ job, onClick }: { job: JobEntry; onClick: () => void }) {
  const initials = (job.company || "?").slice(0, 2).toUpperCase();
  const hue = ((job.company.charCodeAt(0) || 65) * 47) % 360;
  const [logoOk, setLogoOk] = useState(true);
  const showLogo = !!job.logo_url && logoOk;
  return (
    <button onClick={onClick}
      className="w-full text-left px-4 py-2.5 border-b border-slate-100 hover:bg-slate-50 transition-colors">
      <div className="flex items-center gap-3">
        {showLogo ? (
          <img src={job.logo_url} alt={job.company}
            onError={() => setLogoOk(false)}
            className="w-7 h-7 rounded object-contain bg-white border border-slate-100 shrink-0" />
        ) : (
          <div className="w-7 h-7 rounded flex items-center justify-center text-white text-[10px] font-bold shrink-0"
            style={{ backgroundColor: `hsl(${hue},45%,52%)` }}>
            {initials}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-slate-900 text-[13px] truncate">{job.title}</p>
            <span className="text-[11px] text-slate-400 shrink-0">{job.company}</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
            <ClassificationBadge classification={job.classification} />
            {job.failure_reason && (
              <span className="text-[11px] text-slate-400 truncate">{failureLabel(job.failure_reason)}</span>
            )}
          </div>
        </div>
        <ScorePill score={job.score} />
        <StatusBadge status={job.status} />
        {job.url && (
          <a href={job.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
            aria-label="Open job posting" className="text-slate-300 hover:text-indigo-500 shrink-0">
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </button>
  );
}

/* ── Activity timeline ───────────────────────────────────────────────────── */

function ActivityTimeline() {
  const logs = useSessionStore((s) => s.logs);
  const isRunning = useSessionStore((s) => s.isRunning);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  const dot = (l: string) =>
    l === "error" ? "bg-red-400" :
    l === "success" ? "bg-emerald-400" :
    l === "warning" ? "bg-amber-400" : "bg-slate-300";

  return (
    <Card className="flex flex-col overflow-hidden">
      <CardHeader title="Live activity" count={logs.length} />
      <div className="overflow-y-auto flex-1 max-h-[24rem] px-4 py-2">
        {logs.length === 0 ? (
          <EmptyState icon={Activity} title={isRunning ? "Waiting for events…" : "No activity yet"}
            hint={isRunning ? undefined : "Start a session from Setup to see live progress."} />
        ) : (
          <ol className="relative">
            {logs.map((l, i) => (
              <li key={i} className="flex gap-2.5 py-1">
                <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${dot(l.level)}`} />
                <div className="min-w-0">
                  <span className="text-[10px] text-slate-300 font-mono mr-1.5">{l.ts}</span>
                  <span className={`text-xs ${l.level === "error" ? "text-red-600" : "text-slate-600"}`}>{l.msg}</span>
                </div>
              </li>
            ))}
            <div ref={bottomRef} />
          </ol>
        )}
      </div>
    </Card>
  );
}

/* ── Review queue snapshot ───────────────────────────────────────────────── */

function ReviewSnapshot({ queue }: { queue: ReviewQueueResponse | null }) {
  const savedCount = queue?.saved?.length ?? 0;
  const reviewCount = queue?.manual_review.length ?? 0;
  const draftCount = queue?.drafts.length ?? 0;
  return (
    <Card>
      <CardHeader title="Saved & Skipped" right={
        <Link to="/review" className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700">Open →</Link>
      } />
      {savedCount + reviewCount + draftCount === 0 ? (
        <EmptyState icon={Inbox} title="Nothing here yet"
          hint="External-site jobs are saved automatically with their link — they never block the session." />
      ) : (
        <div className="px-4 py-3 grid grid-cols-3 gap-2">
          <Link to="/review" className="border border-sky-200 bg-sky-50 rounded-lg px-3 py-2 hover:bg-sky-100 transition-colors">
            <p className="text-lg font-bold text-sky-700 leading-none">{savedCount}</p>
            <p className="text-[11px] text-sky-600 mt-1">Saved external jobs</p>
          </Link>
          <Link to="/review" className="border border-amber-200 bg-amber-50 rounded-lg px-3 py-2 hover:bg-amber-100 transition-colors">
            <p className="text-lg font-bold text-amber-700 leading-none">{reviewCount}</p>
            <p className="text-[11px] text-amber-600 mt-1">Needs attention</p>
          </Link>
          <Link to="/review" className="border border-teal-200 bg-teal-50 rounded-lg px-3 py-2 hover:bg-teal-100 transition-colors">
            <p className="text-lg font-bold text-teal-700 leading-none">{draftCount}</p>
            <p className="text-[11px] text-teal-600 mt-1">Email drafts</p>
          </Link>
        </div>
      )}
    </Card>
  );
}

interface SystemAlert {
  id: string;
  severity: "error" | "warning";
  title: string;
  detail: string;
}

function AlertBanner({ alert }: { alert: SystemAlert }) {
  const isError = alert.severity === "error";
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 ${
      isError ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
      {isError
        ? <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
        : <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />}
      <div className="min-w-0">
        <p className={`text-xs font-semibold ${isError ? "text-red-700" : "text-amber-700"}`}>{alert.title}</p>
        <p className={`text-[11px] mt-0.5 ${isError ? "text-red-600" : "text-amber-600"}`}>{alert.detail}</p>
      </div>
    </div>
  );
}

function toJobEntry(a: ApplicationRecord): JobEntry {
  return {
    appId: a.id, idx: 0, total: 0,
    title: a.job_title, company: a.company, url: a.job_url,
    // Score is only meaningful once the LLM actually scored the job:
    // show — for unscored rows, and 0 only when the LLM returned 0.
    score: a.recommendation ? a.score : undefined,
    rationale: a.rationale || undefined,
    matched: a.matched_skills, missing: a.missing_skills,
    recommendation: a.recommendation || undefined,
    status: a.status, classification: a.classification || undefined,
    failure_reason: a.failure_reason || undefined,
    external_url: a.external_site_url || undefined,
    exp_required: a.experience_required || undefined,
    salary: a.salary || undefined,
    logo_url: a.company_logo_url || undefined,
    posted_date: a.posted_date || undefined,
  };
}

/* ── Dashboard ───────────────────────────────────────────────────────────── */

export default function DashboardPage() {
  useWebSocket();

  const isRunning = useSessionStore((s) => s.isRunning);
  const uiState = useSessionStore((s) => s.uiState);
  const setRunning = useSessionStore((s) => s.setRunning);
  const setStopped = useSessionStore((s) => s.setStopped);
  const setCounts = useSessionStore((s) => s.setCounts);
  const jobs = useSessionStore((s) => s.jobs);
  const counts = useSessionStore((s) => s.counts);
  const target = useSessionStore((s) => s.target);
  const loginStatus = useSessionStore((s) => s.loginStatus);

  const [stopping, setStopping] = useState(false);
  const [starting, setStarting] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobEntry | null>(null);
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [persistedJobs, setPersistedJobs] = useState<JobEntry[]>([]);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [reportSessionId, setReportSessionId] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  // Poll persisted status/counters — counters always reflect DB rows.
  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const r = await api.get<SessionStatusResponse>("/api/session/status");
        if (!active) return;
        setCounts(r.data.counts ?? {});
        if (r.data.is_running) setRunning(true, r.data.session_id);
        // Hydrate the job table from persisted rows (latest session) so the
        // dashboard survives refreshes and shows final lifecycle states.
        const sessId = r.data.session?.id;
        setReportSessionId(sessId ?? null);
        if (sessId) {
          const h = await api.get<PaginatedApplications>("/api/history", {
            params: { session_id: sessId, per_page: 100 },
          });
          if (active) setPersistedJobs(h.data.records.map(toJobEntry).reverse());
        }
      } catch { /* backend offline */ }
      try {
        const q = await api.get<ReviewQueueResponse>("/api/review/queue");
        if (active) setQueue(q.data);
      } catch { /* ignore */ }
      try {
        const a = await api.get<{ alerts: SystemAlert[] }>("/api/alerts");
        if (active) setAlerts(a.data.alerts ?? []);
      } catch { /* ignore */ }
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => { active = false; clearInterval(id); };
  }, [setCounts, setRunning]);

  async function stopSession() {
    setStopping(true);
    setStopped(); // immediate UI feedback
    try {
      await api.post("/api/session/stop");
    } finally {
      setStopping(false);
    }
  }

  async function startSession() {
    setStarting(true);
    setStartError(null);
    try {
      // Load current config to get user preferences
      const configRes = await api.get<AppConfig>("/api/config");
      const cfg = configRes.data;

      // Get keywords from CV profile if not set
      let keywords: string[] = [];
      try {
        const cvRes = await api.get("/api/cv/profile");
        const cv = cvRes.data;
        keywords = cv.job_titles || [];
      } catch {
        keywords = ["Software Engineer"];
      }

      const payload = {
        platform: cfg.platform || "naukri",
        mode: cfg.mode || "search_and_apply",
        location: cfg.location || "gurugram",
        job_target: cfg.job_target || 5,
        confidence_threshold: cfg.confidence_threshold || 75,
        keywords: keywords,
        easy_apply_only: cfg.easy_apply_only ?? true,
        include_external_review: cfg.include_external_review ?? true,
        outreach_mode: cfg.outreach_mode || "draft_only",
        hide_previously_skipped: cfg.hide_previously_skipped ?? true,
        auto_ignore_skipped: cfg.auto_ignore_skipped ?? true,
        date_posted_filter: cfg.date_posted_filter || "any",
        naukri_search_mode: cfg.naukri_search_mode || "selenium",
      };

      const response = await api.post("/api/session/start", payload);
      setRunning(true, response.data.session_id);
    } catch (e: any) {
      console.error("Failed to start session:", e);
      const detail = e.response?.data?.detail;
      setStartError(typeof detail === 'string' ? detail : detail?.message || e.message || "Failed to start session");
    } finally {
      setStarting(false);
    }
  }

  // Live WS rows take priority; fall back to persisted rows after refresh.
  const tableJobs = jobs.length > 0 ? jobs : persistedJobs;

  const c = (k: string) => counts[k] ?? 0;
  const applied = c("applied") + c("applied_pending_confirmation");
  const inFlight = c("queued") + c("fetching") + c("scoring") + c("applying");
  const reviewable = c("saved") + c("manual_review") + c("email_drafted");
  const failed = c("failed") + c("stopped");
  const total = counts["total"] ?? tableJobs.length;
  const pct = target > 0 ? Math.round((applied / target) * 100) : 0;

  return (
    <div className="p-6 space-y-4 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-900">Command Center</h1>
          <SessionBanner />
        </div>
        <div className="flex items-center gap-2">
          {Object.entries(loginStatus).map(([p, ok]) => (
            <span key={p} className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[11px] font-medium capitalize
              ${ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-600"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />
              {p}
            </span>
          ))}
          {reportSessionId && (
            <a href={`/api/sessions/${reportSessionId}/report.csv`} download
              className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:border-slate-300 bg-white text-slate-600 text-xs font-semibold rounded-lg">
              <Download className="w-3 h-3" /> Export report
            </a>
          )}
          {isRunning ? (
            <button onClick={stopSession} disabled={stopping}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-60
                         text-white text-xs font-semibold rounded-lg">
              {stopping ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3 h-3" />}
              {stopping ? "Stopping…" : "Stop session"}
            </button>
          ) : (
            <button onClick={startSession} disabled={starting}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60
                         text-white text-xs font-semibold rounded-lg">
              {starting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3 h-3" />}
              {starting ? "Starting…" : "Run"}
            </button>
          )}
        </div>
      </div>

      {/* System alerts: broken selectors, missing SMTP, high failure rate */}
      {startError && (
        <AlertBanner alert={{
          id: "start-error",
          severity: "error",
          title: "Failed to start session",
          detail: startError,
        }} />
      )}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a) => <AlertBanner key={a.id} alert={a} />)}
        </div>
      )}

      {/* Summary cards — counters from persisted rows */}
      <div className="grid grid-cols-5 gap-3">
        <SummaryCard label="Applied" value={applied} sub={target ? `${pct}% of target ${target}` : undefined}
          icon={CheckCircle2} tone="text-emerald-500" />
        <SummaryCard label="In progress" value={inFlight} icon={Loader2} tone="text-indigo-500" />
        <SummaryCard label="Saved / attention" value={reviewable} sub="Non-blocking"
          icon={Inbox} tone="text-sky-500" />
        <SummaryCard label="Skipped" value={c("skipped")} icon={XCircle} tone="text-slate-400" />
        <SummaryCard label="Failed / stopped" value={failed} icon={AlertCircle} tone="text-red-500" />
      </div>

      {/* Progress */}
      {target > 0 && (
        <Card className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-600">Progress toward target</span>
            <span className="text-xs font-bold text-slate-900">{applied} / {target} applied</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-700 ${pct >= 100 ? "bg-emerald-500" : "bg-indigo-500"}`}
              style={{ width: `${Math.min(100, pct)}%` }} />
          </div>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-4">
        {/* Job table */}
        <Card className="col-span-2 overflow-hidden">
          <CardHeader title="Jobs this session" count={total} right={
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <ListChecks className="w-3 h-3" /> click a row for details
            </span>
          } />
          <div className="max-h-[28rem] overflow-y-auto">
            {tableJobs.length === 0 ? (
              uiState === "running" ? (
                <EmptyState icon={Search} title="Searching for jobs…"
                  hint="Listings appear here as soon as they are found." />
              ) : uiState === "stopped" ? (
                <EmptyState icon={OctagonX} title="Session stopped"
                  hint="Start a new session from Setup when you're ready." />
              ) : uiState === "failed" ? (
                <EmptyState icon={AlertCircle} title="Session failed"
                  hint="Check the activity timeline for the error, then try again." />
              ) : uiState === "completed" ? (
                <EmptyState icon={CheckCircle2} title="Session finished"
                  hint="No jobs in this run — see History for past sessions." />
              ) : (
                <EmptyState icon={Inbox} title="No active session"
                  hint="Launch a session from Setup to populate the command center."
                  action={<Link to="/setup" className="text-xs font-semibold text-indigo-600 hover:text-indigo-700">Go to Setup →</Link>} />
              )
            ) : (
              tableJobs.map((job, i) => (
                <JobRow key={job.appId ?? `i-${i}`} job={job} onClick={() => setSelectedJob(job)} />
              ))
            )}
          </div>
        </Card>

        {/* Right column */}
        <div className="space-y-4">
          <ReviewSnapshot queue={queue} />
          <ActivityTimeline />
        </div>
      </div>

      {/* Email drafts hint */}
      {c("email_drafted") > 0 && (
        <Card className="px-4 py-3 flex items-center gap-3 border-sky-200">
          <Mail className="w-4 h-4 text-sky-600 shrink-0" />
          <p className="text-xs text-slate-600 flex-1">
            {c("email_drafted")} outreach draft{c("email_drafted") > 1 ? "s" : ""} ready (optional) — drafts are
            never sent automatically.
          </p>
          <Link to="/review" className="text-xs font-semibold text-sky-700 hover:text-sky-800">View drafts →</Link>
        </Card>
      )}

      {selectedJob && <JobDetailDrawer job={selectedJob} onClose={() => setSelectedJob(null)} />}
    </div>
  );
}
