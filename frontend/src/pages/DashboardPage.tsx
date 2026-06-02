import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useWebSocket } from "../hooks/useWebSocket";
import { useSessionStore, type JobEntry } from "../store/sessionStore";

// ── Status badge ──────────────────────────────────────────────────────────────

function Badge({ status }: { status?: string }) {
  const map: Record<string, string> = {
    applied:          "bg-green-100 text-green-800",
    skipped:          "bg-gray-100 text-gray-600",
    skipped_external: "bg-yellow-100 text-yellow-800",
    error:            "bg-red-100 text-red-700",
    pending:          "bg-blue-50 text-blue-500",
  };
  const cls = map[status ?? "pending"] ?? "bg-gray-100 text-gray-500";
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>{status ?? "…"}</span>;
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score?: number }) {
  if (score === undefined) return <span className="text-xs text-gray-400">scoring…</span>;
  const pct = Math.min(100, Math.max(0, score));
  const colour = pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-gray-200 overflow-hidden">
        <div className={`h-2 rounded-full ${colour} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-700 w-7 text-right">{score}</span>
    </div>
  );
}

// ── Skill chips ───────────────────────────────────────────────────────────────

function Chips({ skills, colour }: { skills?: string[]; colour: string }) {
  if (!skills?.length) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {skills.slice(0, 8).map((s) => (
        <span key={s} className={`text-xs px-1.5 py-0.5 rounded ${colour}`}>{s}</span>
      ))}
    </div>
  );
}

// ── Job card (one row in the table) ──────────────────────────────────────────

function JobRow({ job }: { job: JobEntry }) {
  const isLatest = !job.status;
  return (
    <div className={`px-4 py-3 border-b border-gray-100 text-sm ${isLatest ? "bg-blue-50" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-400 w-7">{job.idx}/{job.total}</span>
            <span className="font-medium text-gray-900 truncate">{job.title}</span>
            <span className="text-gray-500">@ {job.company}</span>
            {job.salary && <span className="text-xs text-green-700 bg-green-50 px-1.5 py-0.5 rounded">{job.salary}</span>}
          </div>
          <div className="mt-1.5 w-48">
            <ScoreBar score={job.score} />
          </div>
          {job.rationale && <p className="text-xs text-gray-500 mt-1 line-clamp-1">{job.rationale}</p>}
          <Chips skills={job.matched} colour="bg-green-100 text-green-700" />
          <Chips skills={job.missing} colour="bg-red-100 text-red-600" />
        </div>
        <div className="shrink-0">
          <Badge status={job.status} />
        </div>
      </div>
    </div>
  );
}

// ── Log feed ──────────────────────────────────────────────────────────────────

function LogFeed() {
  const logs    = useSessionStore((s) => s.logs);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  const colour = (level: string) => {
    if (level === "error")   return "text-red-400";
    if (level === "success") return "text-green-400";
    if (level === "warning") return "text-yellow-400";
    return "text-gray-300";
  };

  return (
    <div className="bg-gray-900 rounded-xl overflow-hidden flex flex-col h-64">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <span className="text-xs text-gray-400 font-mono">Live Log</span>
        <span className="text-xs text-gray-500">{logs.length} entries</span>
      </div>
      <div className="overflow-y-auto flex-1 px-4 py-2 font-mono text-xs space-y-0.5">
        {logs.map((l, i) => (
          <div key={i} className={colour(l.level)}>
            <span className="text-gray-600 mr-2">{l.ts}</span>{l.msg}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  useWebSocket();   // connect + auto-reconnect, dispatches to store

  const navigate       = useNavigate();
  const isRunning      = useSessionStore((s) => s.isRunning);
  const loginStatus    = useSessionStore((s) => s.loginStatus);
  const searchCounts   = useSessionStore((s) => s.searchCounts);
  const jobs           = useSessionStore((s) => s.jobs);
  const appliedCount   = useSessionStore((s) => s.appliedCount);
  const target         = useSessionStore((s) => s.target);

  async function handleStop() {
    await api.post("/api/session/stop");
  }

  const totalFound = Object.values(searchCounts).reduce((a, b) => a + b, 0);
  const pct = target > 0 ? Math.round((appliedCount / target) * 100) : 0;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Live Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {isRunning ? "Session in progress…" : "Session ended"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isRunning && (
            <button onClick={handleStop}
              className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700">
              ■ Stop
            </button>
          )}
          <button onClick={() => navigate("/")}
            className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300">
            ← Setup
          </button>
        </div>
      </div>

      {/* Login + stats row */}
      <div className="grid grid-cols-4 gap-4">
        {["naukri", "linkedin"].map((p) => (
          <div key={p} className={`bg-white border rounded-xl px-4 py-3 text-sm shadow-sm ${
            loginStatus[p] === true  ? "border-green-300" :
            loginStatus[p] === false ? "border-red-300"   : "border-gray-200"
          }`}>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5 capitalize">{p}</p>
            <p className={`font-semibold ${
              loginStatus[p] === true  ? "text-green-700" :
              loginStatus[p] === false ? "text-red-600"   : "text-gray-400"
            }`}>
              {loginStatus[p] === true ? "✓ Logged in" : loginStatus[p] === false ? "✗ Failed" : "—"}
            </p>
          </div>
        ))}

        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm shadow-sm">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Found</p>
          <p className="text-xl font-bold text-gray-900">{totalFound}</p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm shadow-sm">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Applied</p>
          <p className="text-xl font-bold text-blue-600">{appliedCount} / {target || "—"}</p>
        </div>
      </div>

      {/* Progress bar */}
      {target > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Progress</span><span>{pct}%</span>
          </div>
          <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-3 bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {/* Jobs table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Jobs Analysed</span>
          <span className="text-xs text-gray-400">{jobs.length} total</span>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {jobs.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-gray-400">
              {isRunning ? "Waiting for search results…" : "No jobs found yet."}
            </div>
          ) : (
            jobs.map((job, i) => <JobRow key={i} job={job} />)
          )}
        </div>
      </div>

      {/* Log feed */}
      <LogFeed />
    </div>
  );
}
