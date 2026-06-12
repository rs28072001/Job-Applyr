import { useCallback, useEffect, useState } from "react";
import {
  Inbox, Mail, ExternalLink, CheckCircle2, XCircle, Loader2,
  Send, Copy, ShieldCheck, Pencil, SkipForward, Bookmark,
} from "lucide-react";
import { api } from "../api/client";
import type { ApplicationRecord, OutreachDraft, ReviewQueueResponse } from "../api/types";
import {
  Card, CardHeader, ClassificationBadge, EmptyState, LoadingState, ScorePill, failureLabel,
} from "../components/ui";

/* ── Manual review row ───────────────────────────────────────────────────── */

function ReviewJobRow({ app, onResolved }: { app: ApplicationRecord; onResolved: () => void }) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  async function resolve(action: "mark_applied" | "dismiss") {
    setBusy(action); setErr("");
    try {
      await api.post(`/api/review/applications/${app.id}/resolve`, { action });
      onResolved();
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      setErr(typeof detail === "string" ? detail : e.message || "Action failed");
    } finally {
      setBusy("");
    }
  }

  const applyUrl = app.external_site_url || app.job_url;

  return (
    <div className="px-4 py-3 border-b border-slate-100">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-slate-900 text-[13px]">{app.job_title}</p>
            <span className="text-[11px] text-slate-400">{app.company}</span>
            <ClassificationBadge classification={app.classification} />
            <ScorePill score={app.score} />
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            {app.status === "saved"
              ? "Saved automatically — apply on the company site whenever you like"
              : failureLabel(app.failure_reason) || "Needs manual handling"}
            {app.location && <> · {app.location}</>}
          </p>
          {app.rationale && <p className="text-[11px] text-slate-400 mt-0.5 italic line-clamp-1">{app.rationale}</p>}
          {err && <p className="text-[11px] text-red-600 mt-1">{err}</p>}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {applyUrl && (
            <a href={applyUrl} target="_blank" rel="noreferrer"
              className="flex items-center gap-1 px-2 py-1.5 border border-slate-200 hover:border-slate-300 rounded-lg text-[11px] font-semibold text-slate-700">
              <ExternalLink className="w-3 h-3" /> Open
            </a>
          )}
          <button onClick={() => resolve("mark_applied")} disabled={!!busy}
            className="flex items-center gap-1 px-2 py-1.5 border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 rounded-lg text-[11px] font-semibold text-emerald-700 disabled:opacity-50">
            {busy === "mark_applied" ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
            I applied
          </button>
          <button onClick={() => resolve("dismiss")} disabled={!!busy}
            className="flex items-center gap-1 px-2 py-1.5 border border-slate-200 hover:bg-slate-50 rounded-lg text-[11px] font-semibold text-slate-500 disabled:opacity-50">
            {busy === "dismiss" ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
            {app.status === "saved" ? "Remove" : "Dismiss"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Draft card ──────────────────────────────────────────────────────────── */

function DraftCard({ draft, sendEnabled, onChanged }: {
  draft: OutreachDraft; sendEnabled: boolean; onChanged: () => void;
}) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [copied, setCopied] = useState(false);

  async function act(action: string, fn: () => Promise<unknown>) {
    setBusy(action); setErr("");
    try {
      await fn();
      onChanged();
    } catch (e: any) {
      setErr(e.response?.data?.detail ?? e.message);
    } finally {
      setBusy("");
    }
  }

  async function copyDraft() {
    await navigator.clipboard.writeText(`To: ${draft.recruiter_email}\nSubject: ${subject}\n\n${body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const approved = draft.status === "approved";

  return (
    <div className="px-4 py-3 border-b border-slate-100">
      <div className="flex items-center gap-2 flex-wrap">
        <Mail className="w-3.5 h-3.5 text-sky-600 shrink-0" />
        <p className="font-medium text-slate-900 text-[13px]">{draft.job_title || "Outreach draft"}</p>
        <span className="text-[11px] text-slate-400">{draft.company}</span>
        <span className={`px-1.5 py-0.5 rounded border text-[11px] font-medium
          ${approved ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-sky-200 bg-sky-50 text-sky-700"}`}>
          {approved ? "Approved — ready" : "Draft — awaiting review"}
        </span>
      </div>
      <p className="text-[11px] text-slate-500 mt-1">
        To: <span className="font-medium text-slate-700">{draft.recruiter_email}</span>
        <span className="text-slate-300 mx-1">·</span>
        found via {draft.email_source === "mailto" ? "visible mailto link" : "visible page text"}
        {draft.email_source_url && (
          <>
            <span className="text-slate-300 mx-1">·</span>
            <a href={draft.email_source_url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">source page</a>
          </>
        )}
      </p>

      {editing ? (
        <div className="mt-2 space-y-2">
          <input value={subject} onChange={(e) => setSubject(e.target.value)}
            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs" />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8}
            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-mono leading-relaxed" />
          <div className="flex gap-1.5">
            <button onClick={() => act("save", async () => {
                await api.put(`/api/outreach/${draft.id}`, { subject, body });
                setEditing(false);
              })}
              className="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-[11px] font-semibold">
              {busy === "save" ? "Saving…" : "Save changes"}
            </button>
            <button onClick={() => { setEditing(false); setSubject(draft.subject); setBody(draft.body); }}
              className="px-2.5 py-1.5 border border-slate-200 rounded-lg text-[11px] font-semibold text-slate-500">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-2 border border-slate-100 bg-slate-50 rounded-lg px-3 py-2">
          <p className="text-xs font-semibold text-slate-700">{subject}</p>
          <p className="text-xs text-slate-500 mt-1 whitespace-pre-line line-clamp-4">{body}</p>
        </div>
      )}

      {err && <p className="text-[11px] text-red-600 mt-1.5">{err}</p>}

      {!editing && (
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          {!approved && (
            <button onClick={() => act("approve", () => api.post(`/api/outreach/${draft.id}/approve`))}
              disabled={!!busy}
              className="flex items-center gap-1 px-2 py-1.5 border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 rounded-lg text-[11px] font-semibold text-emerald-700 disabled:opacity-50">
              {busy === "approve" ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3" />}
              Approve
            </button>
          )}
          {approved && sendEnabled && (
            <button onClick={() => act("send", () => api.post(`/api/outreach/${draft.id}/send`))}
              disabled={!!busy}
              className="flex items-center gap-1 px-2 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-[11px] font-semibold disabled:opacity-50">
              {busy === "send" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
              Send via SMTP
            </button>
          )}
          <button onClick={copyDraft}
            className="flex items-center gap-1 px-2 py-1.5 border border-slate-200 hover:border-slate-300 rounded-lg text-[11px] font-semibold text-slate-600">
            <Copy className="w-3 h-3" /> {copied ? "Copied!" : "Copy"}
          </button>
          <a href={`mailto:${draft.recruiter_email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}
            className="flex items-center gap-1 px-2 py-1.5 border border-slate-200 hover:border-slate-300 rounded-lg text-[11px] font-semibold text-slate-600">
            <Mail className="w-3 h-3" /> Open in mail app
          </a>
          <button onClick={() => act("mark_sent", () => api.post(`/api/outreach/${draft.id}/mark_sent`))}
            disabled={!!busy}
            className="flex items-center gap-1 px-2 py-1.5 border border-teal-200 bg-teal-50 hover:bg-teal-100 rounded-lg text-[11px] font-semibold text-teal-700 disabled:opacity-50">
            <CheckCircle2 className="w-3 h-3" /> I sent it
          </button>
          <button onClick={() => setEditing(true)}
            className="flex items-center gap-1 px-2 py-1.5 border border-slate-200 hover:border-slate-300 rounded-lg text-[11px] font-semibold text-slate-500">
            <Pencil className="w-3 h-3" /> Edit
          </button>
          <button onClick={() => act("discard", () => api.post(`/api/outreach/${draft.id}/discard`))}
            disabled={!!busy}
            className="flex items-center gap-1 px-2 py-1.5 border border-slate-200 hover:bg-slate-50 rounded-lg text-[11px] font-semibold text-slate-400 disabled:opacity-50 ml-auto">
            <XCircle className="w-3 h-3" /> Discard
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [outreachMode, setOutreachMode] = useState("draft_only");

  const refresh = useCallback(async () => {
    try {
      const r = await api.get<ReviewQueueResponse>("/api/review/queue");
      setQueue(r.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    api.get("/api/config").then((r) => setOutreachMode(r.data.outreach_mode ?? "draft_only")).catch(() => {});
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  const sendEnabled = outreachMode === "send_after_approval";

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Saved & Skipped</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Informational only — sessions never wait for anything on this page. External company-site
          jobs are saved automatically with their link; everything else shows why it was skipped.
        </p>
      </div>

      {loading ? (
        <Card><LoadingState label="Loading…" /></Card>
      ) : (
        <>
          <Card className="overflow-hidden">
            <CardHeader title="Saved jobs (external sites)" count={queue?.saved?.length ?? 0} />
            {!queue?.saved?.length ? (
              <EmptyState icon={Bookmark} title="No saved jobs yet"
                hint="Jobs that apply on a company website are saved here automatically with their link. Apply whenever you like — nothing is required." />
            ) : (
              <div className="max-h-[26rem] overflow-y-auto">
                {queue.saved.map((app) => (
                  <ReviewJobRow key={app.id} app={app} onResolved={refresh} />
                ))}
              </div>
            )}
          </Card>

          <Card className="overflow-hidden">
            <CardHeader title="Needs attention" count={queue?.manual_review.length ?? 0} />
            {!queue?.manual_review.length ? (
              <EmptyState icon={Inbox} title="Nothing needs attention"
                hint="Only pages the automation couldn't read (missing apply button, unexpected layout) land here — and they never block the session." />
            ) : (
              queue.manual_review.map((app) => (
                <ReviewJobRow key={app.id} app={app} onResolved={refresh} />
              ))
            )}
          </Card>

          <Card className="overflow-hidden">
            <CardHeader title="Recently skipped" count={queue?.skipped?.length ?? 0} />
            {!queue?.skipped?.length ? (
              <EmptyState icon={SkipForward} title="No skipped jobs yet"
                hint="Jobs skipped for low score, AI skip, title mismatch, duplicates, or unsupported flows appear here with their reason." />
            ) : (
              <div className="max-h-[24rem] overflow-y-auto">
                {queue.skipped.map((app) => <SkippedRow key={app.id} app={app} />)}
              </div>
            )}
          </Card>

          <Card className="overflow-hidden">
            <CardHeader title="Email drafts (optional)" count={queue?.drafts.length ?? 0} right={
              <span className="text-[11px] text-slate-400">
                mode: <span className="font-semibold text-slate-500">{outreachMode.replace(/_/g, " ")}</span>
              </span>
            } />
            {!queue?.drafts.length ? (
              <EmptyState icon={Mail} title="No drafts yet"
                hint="When a visible recruiter email is found on an external job, a draft is generated here for your review — never sent automatically." />
            ) : (
              queue.drafts.map((d) => (
                <DraftCard key={d.id} draft={d} sendEnabled={sendEnabled} onChanged={refresh} />
              ))
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function SkippedRow({ app }: { app: ApplicationRecord }) {
  return (
    <div className="px-4 py-2 border-b border-slate-100 flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium text-slate-800 text-[13px] truncate">{app.job_title}</p>
          <span className="text-[11px] text-slate-400 shrink-0">{app.company}</span>
        </div>
      </div>
      <ScorePill score={app.recommendation ? app.score : undefined} />
      <span className="text-[11px] text-slate-500 bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5 whitespace-nowrap">
        {failureLabel(app.failure_reason) || "Skipped"}
      </span>
      {app.job_url && (
        <a href={app.job_url} target="_blank" rel="noreferrer" aria-label="Open job posting"
           className="text-slate-300 hover:text-indigo-500">
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      )}
    </div>
  );
}
