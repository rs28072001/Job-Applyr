import { X, ExternalLink, Mail } from "lucide-react";
import type { JobEntry } from "../store/sessionStore";
import { ClassificationBadge, ScorePill, StatusBadge, failureLabel } from "./ui";

export default function JobDetailDrawer({ job, onClose }: { job: JobEntry; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 bg-slate-900/20 z-40" onClick={onClose}
           data-testid="drawer-backdrop" />
      <aside className="fixed right-0 top-0 h-full w-[26rem] max-w-full bg-white border-l border-slate-200 z-50 flex flex-col shadow-xl">
        <div className="px-4 py-3 border-b border-slate-100 flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-slate-900 text-sm leading-snug">{job.title}</p>
            <p className="text-xs text-slate-500 mt-0.5">{job.company}</p>
          </div>
          <button onClick={onClose} aria-label="Close details"
                  className="p-1 rounded hover:bg-slate-100 text-slate-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 text-sm">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={job.status} />
            <ClassificationBadge classification={job.classification} />
            <ScorePill score={job.score} />
          </div>

          {job.failure_reason && (
            <div className="border border-amber-200 bg-amber-50 rounded-lg px-3 py-2">
              <p className="text-[11px] font-semibold text-amber-700 uppercase tracking-wide">Reason</p>
              <p className="text-xs text-amber-800 mt-0.5">{failureLabel(job.failure_reason)}</p>
            </div>
          )}

          {(job.exp_required || job.salary) && (
            <div className="grid grid-cols-2 gap-2 text-xs">
              {job.exp_required && (
                <div className="border border-slate-200 rounded-lg px-2.5 py-1.5">
                  <p className="text-slate-400 text-[11px]">Experience</p>
                  <p className="text-slate-700 font-medium">{job.exp_required}</p>
                </div>
              )}
              {job.salary && (
                <div className="border border-slate-200 rounded-lg px-2.5 py-1.5">
                  <p className="text-slate-400 text-[11px]">Salary</p>
                  <p className="text-slate-700 font-medium">{job.salary}</p>
                </div>
              )}
            </div>
          )}

          {job.recommendation && (
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">AI assessment</p>
              <p className="text-xs text-slate-600">
                Recommendation: <span className="font-semibold">{job.recommendation}</span>
                {job.score !== undefined && <> · score {job.score}</>}
              </p>
              {job.rationale && <p className="text-xs text-slate-500 mt-1 italic">{job.rationale}</p>}
            </div>
          )}

          {!!job.matched?.length && (
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">Matched skills</p>
              <div className="flex flex-wrap gap-1">
                {job.matched.map((s) => (
                  <span key={s} className="px-1.5 py-0.5 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 text-[11px]">{s}</span>
                ))}
              </div>
            </div>
          )}
          {!!job.missing?.length && (
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">Missing skills</p>
              <div className="flex flex-wrap gap-1">
                {job.missing.map((s) => (
                  <span key={s} className="px-1.5 py-0.5 rounded border border-red-200 bg-red-50 text-red-600 text-[11px]">{s}</span>
                ))}
              </div>
            </div>
          )}

          {job.status === "email_drafted" && (
            <div className="border border-sky-200 bg-sky-50 rounded-lg px-3 py-2 flex items-start gap-2">
              <Mail className="w-3.5 h-3.5 text-sky-600 mt-0.5 shrink-0" />
              <p className="text-xs text-sky-800">
                An outreach email draft was created for this job. Review and approve it in the Review Queue — nothing is sent automatically.
              </p>
            </div>
          )}
        </div>

        <div className="px-4 py-3 border-t border-slate-100 flex gap-2">
          {job.url && (
            <a href={job.url} target="_blank" rel="noreferrer"
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-slate-200 hover:border-slate-300 rounded-lg text-xs font-semibold text-slate-700">
              <ExternalLink className="w-3.5 h-3.5" /> Open job
            </a>
          )}
          {job.external_url && (
            <a href={job.external_url} target="_blank" rel="noreferrer"
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-amber-200 bg-amber-50 hover:bg-amber-100 rounded-lg text-xs font-semibold text-amber-700">
              <ExternalLink className="w-3.5 h-3.5" /> Company site
            </a>
          )}
        </div>
      </aside>
    </>
  );
}
