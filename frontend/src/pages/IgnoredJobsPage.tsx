import { useEffect, useState } from "react";
import { Download, ExternalLink, RotateCcw, Trash2, Ban } from "lucide-react";
import { api } from "../api/client";
import type { IgnoredJob, IgnoredJobsResponse } from "../api/types";
import { Card, CardHeader, EmptyState, LoadingState, failureLabel } from "../components/ui";

function fmtDate(value: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString("en-IN", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

function IgnoredRow({ row, onChanged }: { row: IgnoredJob; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);

  async function unignore() {
    setBusy(true);
    try {
      await api.delete(`/api/ignored-jobs/${row.id}`);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{fmtDate(row.ignored_at)}</td>
      <td className="px-4 py-3">
        <p className="text-sm font-semibold text-slate-900">{row.job_title || "Untitled job"}</p>
        <p className="text-xs text-slate-400">{row.company || "Unknown company"} · {row.platform || "platform"}</p>
      </td>
      <td className="px-4 py-3 text-xs text-slate-500">
        <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5">
          {row.ignore_type.replace(/_/g, " ")}
        </span>
        <p className="mt-1">{failureLabel(row.ignore_reason) || row.ignore_reason || "Ignored"}</p>
      </td>
      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{row.score || "—"}</td>
      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{fmtDate(row.expires_at)}</td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2">
          {row.job_url && (
            <a href={row.job_url} target="_blank" rel="noreferrer"
              className="text-slate-300 hover:text-indigo-500" title="Open job">
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
          <button onClick={unignore} disabled={busy}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-50">
            <RotateCcw className="h-3 w-3" /> Unignore
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function IgnoredJobsPage() {
  const [rows, setRows] = useState<IgnoredJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);

  async function refresh() {
    const r = await api.get<IgnoredJobsResponse>("/api/ignored-jobs");
    setRows(r.data.records);
    setTotal(r.data.total);
    setLoading(false);
  }

  useEffect(() => { refresh().catch(() => setLoading(false)); }, []);

  async function clearExpired() {
    setClearing(true);
    try {
      await api.post("/api/ignored-jobs/clear-expired");
      await refresh();
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Ignored Jobs</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Local sheet of jobs skipped before. Active rows are skipped before scoring so repeats stay out of new runs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={clearExpired} disabled={clearing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-300 disabled:opacity-50">
            <Trash2 className="h-3 w-3" /> {clearing ? "Clearing…" : "Clear expired"}
          </button>
          <a href="/api/ignored-jobs/export.csv" download
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-300">
            <Download className="h-3 w-3" /> Export CSV
          </a>
        </div>
      </div>

      <Card className="overflow-hidden">
        <CardHeader title="Active ignored jobs" count={total} />
        {loading ? (
          <LoadingState label="Loading ignored jobs…" />
        ) : rows.length === 0 ? (
          <EmptyState icon={Ban} title="No ignored jobs yet"
            hint="Stable skips are added here automatically when the setup toggle is enabled." />
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-left">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Ignored</th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Job</th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Reason</th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Score</th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Expires</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => <IgnoredRow key={row.id} row={row} onChanged={refresh} />)}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
