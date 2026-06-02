import { useState, useEffect } from "react";
import { api } from "../api/client";
import type { SessionRecord, ApplicationRecord, PaginatedApplications } from "../api/types";

function StatusDot({ status }: { status: string }) {
  const m: Record<string, string> = {
    completed: "bg-green-500", running: "bg-blue-500",
    stopped: "bg-yellow-500", failed: "bg-red-500",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${m[status] ?? "bg-gray-400"}`} />;
}

function AppBadge({ status }: { status: string }) {
  const m: Record<string, string> = {
    applied: "bg-green-100 text-green-800",
    skipped: "bg-gray-100 text-gray-600",
    skipped_external: "bg-yellow-100 text-yellow-800",
    error: "bg-red-100 text-red-700",
  };
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${m[status] ?? "bg-gray-100"}`}>{status}</span>;
}

export default function HistoryPage() {
  const [sessions, setSessions]     = useState<SessionRecord[]>([]);
  const [selected, setSelected]     = useState<number | null>(null);
  const [apps, setApps]             = useState<ApplicationRecord[]>([]);
  const [total, setTotal]           = useState(0);
  const [page, setPage]             = useState(1);
  const [statusFilter, setStatus]   = useState("");
  const PER_PAGE = 25;

  useEffect(() => {
    api.get<SessionRecord[]>("/api/history/sessions").then((r) => setSessions(r.data));
  }, []);

  useEffect(() => {
    if (selected === null) return;
    const params: Record<string, unknown> = { session_id: selected, page, per_page: PER_PAGE };
    if (statusFilter) params.status = statusFilter;
    api.get<PaginatedApplications>("/api/history", { params }).then((r) => {
      setApps(r.data.records);
      setTotal(r.data.total);
    });
  }, [selected, page, statusFilter]);

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">History</h1>

      <div className="grid grid-cols-3 gap-6">
        {/* Sessions sidebar */}
        <div className="col-span-1 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-700">Sessions</span>
          </div>
          <div className="overflow-y-auto max-h-[70vh]">
            {sessions.length === 0 && (
              <p className="text-sm text-gray-400 text-center py-8">No sessions yet.</p>
            )}
            {sessions.map((s) => (
              <button key={s.id} onClick={() => { setSelected(s.id); setPage(1); }}
                className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 text-sm transition-colors ${
                  selected === s.id ? "bg-blue-50 border-l-2 border-l-blue-500" : ""
                }`}>
                <div className="flex items-center gap-2">
                  <StatusDot status={s.status} />
                  <span className="font-medium text-gray-800 capitalize">{s.platform}</span>
                  <span className="text-gray-400 text-xs">{new Date(s.started_at).toLocaleDateString()}</span>
                </div>
                <div className="mt-0.5 flex gap-3 text-xs text-gray-500">
                  <span>✓ {s.applied}</span>
                  <span>○ {s.skipped}</span>
                  <span>target {s.job_target}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Applications table */}
        <div className="col-span-2 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          {selected === null ? (
            <div className="flex items-center justify-center h-64 text-sm text-gray-400">
              ← Select a session to view applications
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-gray-700">Applications ({total})</span>
                <select value={statusFilter} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
                  className="border border-gray-300 rounded-lg px-2 py-1 text-xs">
                  <option value="">All statuses</option>
                  <option value="applied">Applied</option>
                  <option value="skipped">Skipped</option>
                  <option value="skipped_external">External ATS</option>
                  <option value="error">Error</option>
                </select>
              </div>

              <div className="overflow-y-auto max-h-[65vh]">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-4 py-2 text-left">Job</th>
                      <th className="px-4 py-2 text-left">Score</th>
                      <th className="px-4 py-2 text-left">Status</th>
                      <th className="px-4 py-2 text-left">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apps.map((a) => (
                      <tr key={a.id} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2">
                          <a href={a.job_url} target="_blank" rel="noreferrer"
                            className="font-medium text-blue-600 hover:underline line-clamp-1">{a.job_title}</a>
                          <p className="text-xs text-gray-500">{a.company}</p>
                        </td>
                        <td className="px-4 py-2">
                          <span className={`font-bold ${a.score >= 75 ? "text-green-600" : a.score >= 50 ? "text-yellow-600" : "text-red-500"}`}>
                            {a.score}
                          </span>
                        </td>
                        <td className="px-4 py-2"><AppBadge status={a.status} /></td>
                        <td className="px-4 py-2 text-xs text-gray-400">
                          {new Date(a.timestamp).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {total > PER_PAGE && (
                <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                  <span>Page {page} of {Math.ceil(total / PER_PAGE)}</span>
                  <div className="flex gap-2">
                    <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}
                      className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-50">←</button>
                    <button disabled={page >= Math.ceil(total / PER_PAGE)} onClick={() => setPage((p) => p + 1)}
                      className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-50">→</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
