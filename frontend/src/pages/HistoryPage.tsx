import { useState, useEffect } from "react";
import { History, ExternalLink, Clock, Filter, Download } from "lucide-react";
import { api } from "../api/client";
import type { SessionRecord, ApplicationRecord, PaginatedApplications } from "../api/types";
import { ScorePill, StatusBadge, failureLabel } from "../components/ui";

function statusMeta(s: string) {
  if (s === "completed") return { color:"text-emerald-600", bg:"bg-emerald-50", border:"border-emerald-200", dot:"bg-emerald-500" };
  if (s === "running")   return { color:"text-blue-600",    bg:"bg-blue-50",    border:"border-blue-200",    dot:"bg-blue-500 animate-pulse" };
  if (s === "stopped")   return { color:"text-amber-600",   bg:"bg-amber-50",   border:"border-amber-200",   dot:"bg-amber-500" };
  return                        { color:"text-red-600",     bg:"bg-red-50",     border:"border-red-200",     dot:"bg-red-500" };
}

const STATUS_FILTERS = [
  "applied", "applied_pending_confirmation", "skipped", "manual_review",
  "email_drafted", "email_sent", "failed", "stopped",
];

export default function HistoryPage() {
  const [sessions, setSessions]   = useState<SessionRecord[]>([]);
  const [selected, setSelected]   = useState<number | null>(null);
  const [apps, setApps]           = useState<ApplicationRecord[]>([]);
  const [total, setTotal]         = useState(0);
  const [page, setPage]           = useState(1);
  const [statusFilter, setStatus] = useState("");
  const PER_PAGE = 20;

  useEffect(() => {
    api.get<SessionRecord[]>("/api/history/sessions").then((r) => setSessions(r.data));
  }, []);

  useEffect(() => {
    if (selected === null) return;
    const params: Record<string, unknown> = { session_id: selected, page, per_page: PER_PAGE };
    if (statusFilter) params.status = statusFilter;
    api.get<PaginatedApplications>("/api/history", { params }).then((r) => {
      setApps(r.data.records); setTotal(r.data.total);
    });
  }, [selected, page, statusFilter]);

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">History</h1>
        <p className="text-slate-500 text-sm mt-1">All past job search sessions and applications</p>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Sessions sidebar */}
        <div className="col-span-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3.5 border-b border-slate-100 flex items-center gap-2">
              <History className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-semibold text-slate-800">Sessions</span>
              <span className="ml-auto bg-slate-100 text-slate-500 text-xs px-2 py-0.5 rounded-full">{sessions.length}</span>
            </div>
            <div className="overflow-y-auto max-h-[calc(100vh-14rem)]">
              {sessions.length === 0 && (
                <div className="flex flex-col items-center py-12 text-slate-400">
                  <Clock className="w-8 h-8 mb-2 opacity-30" />
                  <p className="text-sm">No sessions yet</p>
                  <p className="text-xs mt-1 text-slate-300">Run a session to see history</p>
                </div>
              )}
              {sessions.map((s) => {
                const meta = statusMeta(s.status);
                const isSelected = selected === s.id;
                return (
                  <button key={s.id} onClick={() => { setSelected(s.id); setPage(1); setStatus(""); }}
                    className={`w-full text-left px-4 py-3.5 border-b border-slate-100 hover:bg-slate-50
                               transition-colors ${isSelected ? "bg-indigo-50 border-l-2 border-l-indigo-500" : ""}`}>
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${meta.dot}`} />
                      <span className="font-semibold text-sm text-slate-900 capitalize">{s.platform}</span>
                      <span className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full border ${meta.bg} ${meta.border} ${meta.color}`}>
                        {s.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-1 mt-2">
                      <div className="bg-emerald-50 rounded-lg px-2 py-1 text-center">
                        <p className="text-emerald-700 font-bold text-sm">{s.applied}</p>
                        <p className="text-emerald-600 text-xs">applied</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg px-2 py-1 text-center">
                        <p className="text-slate-600 font-bold text-sm">{s.skipped}</p>
                        <p className="text-slate-500 text-xs">skipped</p>
                      </div>
                      <div className="bg-slate-50 rounded-lg px-2 py-1 text-center">
                        <p className="text-slate-600 font-bold text-sm">{s.job_target}</p>
                        <p className="text-slate-500 text-xs">target</p>
                      </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                      {new Date(s.started_at).toLocaleDateString("en-IN", { day:"numeric", month:"short", year:"numeric" })}
                      {" · "}
                      {new Date(s.started_at).toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit" })}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Applications table */}
        <div className="col-span-8">
          {selected === null ? (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm
                            flex flex-col items-center justify-center h-64 text-slate-400">
              <History className="w-10 h-10 mb-3 opacity-20" />
              <p className="text-sm font-medium">Select a session to view applications</p>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              {/* Toolbar */}
              <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-3">
                <h2 className="text-sm font-semibold text-slate-800 flex-1">
                  Applications
                  <span className="ml-2 text-slate-400 font-normal">({total})</span>
                </h2>
                <a href={`/api/sessions/${selected}/report.csv`} download
                  className="flex items-center gap-1.5 px-2.5 py-1.5 border border-slate-200 hover:border-slate-300 bg-white text-slate-600 text-xs font-semibold rounded-lg">
                  <Download className="w-3 h-3" /> Export CSV
                </a>
                <div className="flex items-center gap-2">
                  <Filter className="w-3.5 h-3.5 text-slate-400" />
                  <select value={statusFilter} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
                    className="border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-600
                               bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <option value="">All statuses</option>
                    {STATUS_FILTERS.map((s) => (
                      <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Table */}
              <div className="overflow-auto max-h-[calc(100vh-18rem)]">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Job</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wide">Score</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {apps.length === 0 && (
                      <tr><td colSpan={4} className="px-5 py-8 text-center text-slate-400 text-sm">No applications found</td></tr>
                    )}
                    {apps.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0"
                                 style={{ backgroundColor: `hsl(${(a.company.charCodeAt(0)*47)%360},50%,55%)` }}>
                              {a.company.slice(0,2).toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <a href={a.job_url} target="_blank" rel="noreferrer"
                                 className="font-semibold text-slate-900 hover:text-indigo-600 flex items-center gap-1 group">
                                <span className="truncate max-w-[200px]">{a.job_title}</span>
                                <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 shrink-0" />
                              </a>
                              <p className="text-xs text-slate-400 truncate">{a.company}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3.5 text-center">
                          <ScorePill score={a.recommendation ? a.score : undefined} />
                        </td>
                        <td className="px-4 py-3.5">
                          <StatusBadge status={a.status} />
                          {a.failure_reason && (
                            <p className="text-[11px] text-slate-400 mt-0.5">{failureLabel(a.failure_reason)}</p>
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-xs text-slate-400 whitespace-nowrap">
                          {new Date(a.timestamp).toLocaleDateString("en-IN", { day:"numeric", month:"short" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, total)} of {total}
                  </span>
                  <div className="flex gap-1">
                    {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map((p) => (
                      <button key={p} onClick={() => setPage(p)}
                        className={`w-7 h-7 rounded-lg text-xs font-medium transition-colors ${
                          p === page ? "bg-indigo-600 text-white" : "text-slate-500 hover:bg-slate-100"
                        }`}>
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
