import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Square, ArrowLeft, ExternalLink, TrendingUp, CheckCircle2, XCircle, AlertCircle, Clock } from "lucide-react";
import { api } from "../api/client";
import { useWebSocket } from "../hooks/useWebSocket";
import { useSessionStore, type JobEntry } from "../store/sessionStore";

/* ── Stat card ──────────────────────────────────────────────────────────── */
function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: string | number; icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</p>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className="text-3xl font-extrabold text-slate-900">{value}</p>
    </div>
  );
}

/* ── Login chip ─────────────────────────────────────────────────────────── */
function LoginChip({ platform, status }: { platform: string; status?: boolean }) {
  const cfg = status === true  ? { bg:"bg-emerald-50",  border:"border-emerald-200", dot:"bg-emerald-500",  text:"text-emerald-700", label:"✓ Logged in"  }
            : status === false ? { bg:"bg-red-50",      border:"border-red-200",     dot:"bg-red-500",     text:"text-red-700",     label:"✗ Failed"     }
            :                    { bg:"bg-slate-50",    border:"border-slate-200",   dot:"bg-slate-300",   text:"text-slate-500",   label:"Waiting…"     };
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${cfg.bg} ${cfg.border}`}>
      <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot} ${status === undefined ? "animate-pulse" : ""}`} />
      <span className={`text-xs font-semibold capitalize ${cfg.text}`}>{platform}</span>
      <span className={`text-xs ${cfg.text} opacity-80`}>{cfg.label}</span>
    </div>
  );
}

/* ── Score bar ──────────────────────────────────────────────────────────── */
function ScoreBar({ score }: { score?: number }) {
  if (score === undefined) return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full w-1/3 bg-slate-200 rounded-full animate-pulse" />
      </div>
      <span className="text-xs text-slate-400 w-6">…</span>
    </div>
  );
  const color = score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-amber-400" : "bg-red-400";
  const textColor = score >= 75 ? "text-emerald-600" : score >= 50 ? "text-amber-600" : "text-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`}
             style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className={`text-xs font-bold w-6 text-right ${textColor}`}>{score}</span>
    </div>
  );
}

/* ── Status badge ───────────────────────────────────────────────────────── */
function StatusBadge({ status }: { status?: string }) {
  const map: Record<string, string> = {
    applied:          "bg-emerald-100 text-emerald-700 border border-emerald-200",
    skipped:          "bg-slate-100 text-slate-500 border border-slate-200",
    skipped_external: "bg-amber-50 text-amber-700 border border-amber-200",
    error:            "bg-red-50 text-red-600 border border-red-200",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${map[status ?? ""] ?? "bg-blue-50 text-blue-500 border border-blue-100"}`}>
      {status ?? "analysing"}
    </span>
  );
}

/* ── Skill chips ─────────────────────────────────────────────────────────── */
function Skills({ items, color }: { items?: string[]; color: string }) {
  if (!items?.length) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1.5">
      {items.slice(0, 6).map((s) => (
        <span key={s} className={`text-xs px-1.5 py-0.5 rounded-md ${color}`}>{s}</span>
      ))}
    </div>
  );
}

/* ── Job row ─────────────────────────────────────────────────────────────── */
function JobRow({ job, isNew }: { job: JobEntry; isNew: boolean }) {
  const initials = (job.company || "?").slice(0, 2).toUpperCase();
  const hue = ((job.company.charCodeAt(0) || 65) * 47) % 360;
  const [imgError, setImgError] = React.useState(false);
  const showLogo = job.logo_url && !imgError;

  return (
    <div className={`px-5 py-4 border-b border-slate-100 hover:bg-slate-50/50 transition-colors
                     ${isNew ? "bg-indigo-50/30" : ""}`}>
      <div className="flex items-start gap-4">
        {/* Company avatar — real logo if available, else initials */}
        {showLogo ? (
          <img
            src={job.logo_url}
            alt={job.company}
            onError={() => setImgError(true)}
            className="w-9 h-9 rounded-xl object-contain bg-white border border-slate-100 shrink-0"
          />
        ) : (
          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold shrink-0"
               style={{ backgroundColor: `hsl(${hue},55%,55%)` }}>
            {initials}
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="min-w-0">
              <p className="font-semibold text-slate-900 text-sm truncate">{job.title}</p>
              <p className="text-xs text-slate-500">{job.company}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-slate-400">{job.idx}/{job.total}</span>
              <StatusBadge status={job.status} />
              {job.url && (
                <a href={job.url} target="_blank" rel="noreferrer"
                   className="text-slate-300 hover:text-indigo-500">
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>

          <div className="mt-2 max-w-xs">
            <ScoreBar score={job.score} />
          </div>

          {job.rationale && (
            <p className="text-xs text-slate-400 mt-1.5 line-clamp-1 italic">{job.rationale}</p>
          )}

          <Skills items={job.matched} color="bg-emerald-50 text-emerald-700" />
          <Skills items={job.missing} color="bg-red-50 text-red-600" />
        </div>
      </div>
    </div>
  );
}

/* ── Log feed ─────────────────────────────────────────────────────────────── */
function LogFeed() {
  const logs     = useSessionStore((s) => s.logs);
  const bottomRef= useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  const lvlColor = (l: string) =>
    l === "error"   ? "text-red-400" :
    l === "success" ? "text-emerald-400" :
    l === "warning" ? "text-amber-400" : "text-slate-400";

  return (
    <div className="bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
        </div>
        <span className="text-slate-500 text-xs font-mono ml-1">live log</span>
        <span className="ml-auto text-slate-600 text-xs font-mono">{logs.length} lines</span>
      </div>
      <div className="overflow-y-auto max-h-64 px-4 py-3 font-mono text-xs space-y-0.5">
        {logs.length === 0 ? (
          <p className="text-slate-600 italic">Waiting for session events…</p>
        ) : (
          logs.map((l, i) => (
            <div key={i}>
              <span className="text-slate-700 select-none mr-2">{l.ts}</span>
              <span className={lvlColor(l.level)}>{l.msg}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

/* ── Dashboard page ────────────────────────────────────────────────────── */

export default function DashboardPage() {
  useWebSocket();

  const navigate     = useNavigate();
  const isRunning    = useSessionStore((s) => s.isRunning);
  const setRunning   = useSessionStore((s) => s.setRunning);
  const loginStatus  = useSessionStore((s) => s.loginStatus);
  const [stopping, setStopping] = useState(false);

  // Sync running state from backend on mount (handles page refresh)
  useEffect(() => {
    fetch("/api/session/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { is_running: boolean; session_id: number | null } | null) => {
        if (data?.is_running) setRunning(true, data.session_id);
      })
      .catch(() => {});
  }, [setRunning]);
  const jobs         = useSessionStore((s) => s.jobs);
  const appliedCount = useSessionStore((s) => s.appliedCount);
  const target       = useSessionStore((s) => s.target);
  const logs         = useSessionStore((s) => s.logs);

  const applied   = jobs.filter((j) => j.status === "applied").length;
  const skipped   = jobs.filter((j) => j.status?.startsWith("skipped")).length;
  const errors    = jobs.filter((j) => j.status === "error").length;
  const pct       = target > 0 ? Math.round(((appliedCount || applied) / target) * 100) : 0;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate("/setup")}
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-500">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900">Live Dashboard</h1>
              {isRunning && (
                <span className="inline-flex items-center gap-1.5 bg-emerald-50 border border-emerald-200
                                 text-emerald-700 text-xs font-semibold px-2.5 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                  Running
                </span>
              )}
              {!isRunning && logs.length > 0 && (
                <span className="inline-flex items-center gap-1.5 bg-slate-100 border border-slate-200
                                 text-slate-600 text-xs font-semibold px-2.5 py-1 rounded-full">
                  Completed
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-0.5">Real-time job application progress</p>
          </div>
        </div>
        {isRunning && (
          <button onClick={async () => {
              setStopping(true);
              try {
                await api.post("/api/session/stop");
                setRunning(false, null);
              } finally {
                setStopping(false);
              }
            }}
            disabled={stopping}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700
                       disabled:opacity-60 disabled:hover:bg-red-600
                       text-white text-sm font-semibold rounded-xl shadow-sm shadow-red-200">
            <Square className="w-3.5 h-3.5" /> {stopping ? "Stopping..." : "Stop session"}
          </button>
        )}
      </div>

      {/* Login status */}
      <div className="flex gap-3 flex-wrap">
        {["naukri", "linkedin"].map((p) => (
          <LoginChip key={p} platform={p} status={loginStatus[p]} />
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Analysed"  value={jobs.length} icon={TrendingUp}     color="bg-indigo-50 text-indigo-600" />
        <StatCard label="Applied"   value={applied}      icon={CheckCircle2}   color="bg-emerald-50 text-emerald-600" />
        <StatCard label="Skipped"   value={skipped}      icon={XCircle}        color="bg-slate-100 text-slate-500" />
        <StatCard label="Errors"    value={errors}       icon={AlertCircle}    color="bg-red-50 text-red-500" />
      </div>

      {/* Progress bar */}
      {target > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-semibold text-slate-700">Progress toward target</span>
            </div>
            <span className="text-sm font-bold text-slate-900">{appliedCount || applied} / {target} applied</span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-700
              ${pct >= 100 ? "bg-emerald-500" : "bg-indigo-500"}`}
              style={{ width: `${Math.min(100, pct)}%` }} />
          </div>
          <p className="text-xs text-slate-400 mt-1.5">{pct}% complete</p>
        </div>
      )}

      {/* Jobs table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800">Jobs Analysed</h2>
          <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{jobs.length}</span>
        </div>
        <div className="max-h-[28rem] overflow-y-auto">
          {jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <TrendingUp className="w-10 h-10 mb-3 opacity-20" />
              <p className="text-sm">{isRunning ? "Searching for jobs…" : "No jobs found yet"}</p>
            </div>
          ) : (
            jobs.map((job, i) => (
              <JobRow key={i} job={job} isNew={i === jobs.length - 1 && isRunning} />
            ))
          )}
        </div>
      </div>

      {/* Log feed */}
      <LogFeed />
    </div>
  );
}
