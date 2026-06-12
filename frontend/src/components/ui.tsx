import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

/* Restrained SaaS atoms — white surfaces, subtle borders, 8px radius. */

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-lg border border-slate-200 ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, count, right }: { title: string; count?: number; right?: ReactNode }) {
  return (
    <div className="px-4 py-2.5 border-b border-slate-100 flex items-center gap-2">
      <h2 className="text-[13px] font-semibold text-slate-800">{title}</h2>
      {count !== undefined && (
        <span className="text-[11px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{count}</span>
      )}
      {right && <div className="ml-auto">{right}</div>}
    </div>
  );
}

/* ── Status badges ───────────────────────────────────────────────────────── */

const STATUS_STYLES: Record<string, { cls: string; label: string; pulse?: boolean }> = {
  queued:        { cls: "bg-slate-50 text-slate-500 border-slate-200",     label: "Queued" },
  fetching:      { cls: "bg-blue-50 text-blue-600 border-blue-200",        label: "Fetching", pulse: true },
  scoring:       { cls: "bg-indigo-50 text-indigo-600 border-indigo-200",  label: "Scoring", pulse: true },
  applying:      { cls: "bg-violet-50 text-violet-600 border-violet-200",  label: "Applying", pulse: true },
  applied:       { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", label: "Applied" },
  applied_pending_confirmation:
                 { cls: "bg-emerald-50 text-emerald-700 border-emerald-200 border-dashed", label: "Applied (pending)" },
  skipped:       { cls: "bg-slate-100 text-slate-500 border-slate-200",    label: "Skipped" },
  saved:         { cls: "bg-sky-50 text-sky-700 border-sky-200",           label: "Saved" },
  manual_review: { cls: "bg-amber-50 text-amber-700 border-amber-200",     label: "Needs attention" },
  email_drafted: { cls: "bg-sky-50 text-sky-700 border-sky-200",           label: "Email drafted" },
  email_sent:    { cls: "bg-teal-50 text-teal-700 border-teal-200",        label: "Email sent" },
  failed:        { cls: "bg-red-50 text-red-600 border-red-200",           label: "Failed" },
  stopped:       { cls: "bg-orange-50 text-orange-600 border-orange-200",  label: "Stopped" },
};

export function StatusBadge({ status }: { status?: string }) {
  const meta = STATUS_STYLES[status ?? ""] ?? {
    cls: "bg-slate-50 text-slate-400 border-slate-200",
    label: status || "—",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[11px] font-medium whitespace-nowrap ${meta.cls}`}>
      {meta.pulse && <span className="w-1 h-1 rounded-full bg-current animate-pulse" />}
      {meta.label}
    </span>
  );
}

const CLASSIFICATION_LABELS: Record<string, string> = {
  platform_easy_apply: "Easy Apply",
  platform_internal_apply: "Internal apply",
  external_ats: "External ATS",
  email_outreach_candidate: "Email outreach",
  manual_review: "Needs review",
  unsupported: "Unsupported",
};

export function ClassificationBadge({ classification }: { classification?: string }) {
  if (!classification) return null;
  return (
    <span className="inline-block px-1.5 py-0.5 rounded border border-slate-200 bg-slate-50 text-slate-500 text-[11px] whitespace-nowrap">
      {CLASSIFICATION_LABELS[classification] ?? classification}
    </span>
  );
}

export const FAILURE_REASON_LABELS: Record<string, string> = {
  login_required: "Login required",
  apply_button_not_found: "Apply button not found",
  external_site: "External company site",
  captcha_or_challenge: "CAPTCHA / security challenge",
  confirmation_missing: "No confirmation after apply",
  unsupported_flow: "Unsupported apply flow",
  rate_limited: "Rate limit reached",
  scoring_failed: "Scoring failed",
  browser_error: "Browser error",
  already_applied: "Already applied",
  low_score: "Low score",
  ai_skip: "AI skip",
  title_mismatch: "Title mismatch",
  unsupported: "Unsupported",
  session_stopped: "Session stopped",
  duplicate_company: "Already contacted this company recently",
  ignored_previous_skip: "Skipped before",
  posted_date_out_of_range: "Outside date posted filter",
  daily_cap_reached: "Daily apply cap reached",
  // legacy values from older sessions
  below_threshold: "Low score",
  llm_recommended_skip: "AI skip",
};

export function failureLabel(reason?: string): string {
  if (!reason) return "";
  return FAILURE_REASON_LABELS[reason] ?? reason.replace(/_/g, " ");
}

/* ── States ──────────────────────────────────────────────────────────────── */

export function EmptyState({ icon: Icon, title, hint, action }: {
  icon: React.ElementType; title: string; hint?: string; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
      <Icon className="w-8 h-8 mb-3 text-slate-300" />
      <p className="text-sm font-medium text-slate-500">{title}</p>
      {hint && <p className="text-xs text-slate-400 mt-1 max-w-xs">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-slate-400">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ScorePill({ score }: { score?: number }) {
  if (score === undefined || score === null)
    return <span className="text-[11px] text-slate-300">—</span>;
  const cls = score >= 75 ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : score >= 50 ? "bg-amber-50 text-amber-700 border-amber-200"
    : "bg-red-50 text-red-600 border-red-200";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded border text-[11px] font-semibold ${cls}`}>
      {score}
    </span>
  );
}

export function LocalOnlyNote({ text = "Stored locally on this machine only — never uploaded." }: { text?: string }) {
  return (
    <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
      {text}
    </p>
  );
}
