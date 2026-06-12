import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload, CheckCircle2, AlertCircle, Loader2, Play, ArrowRight, ArrowLeft,
  User, Mail, Phone, Briefcase, Star, Key, Cpu, FileText, Sliders, ShieldCheck,
} from "lucide-react";
// (Mail icon reused for the SMTP test button)
import { api } from "../api/client";
import type { AppConfig, CVProfile, OutreachMode, SessionStartRequest } from "../api/types";
import { useSessionStore } from "../store/sessionStore";
import { Card, LocalOnlyNote } from "../components/ui";

/* ── Shared atoms ─────────────────────────────────────────────────────────── */

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">{children}</label>;
}

const inputCls = `w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
  focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
  hover:border-slate-300 bg-white text-slate-900 placeholder-slate-400`;

const SECRET_MASK = "***";
const SECRET_FIELDS = [
  "naukri_password", "linkedin_password", "azure_openai_api_key",
  "openai_api_key", "gemini_api_key", "groq_api_key", "openrouter_api_key",
  "smtp_password",
];

const AI_PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI", key: "openai_api_key", model: "openai_model", modelPlaceholder: "gpt-4o-mini" },
  { value: "gemini", label: "Gemini", key: "gemini_api_key", model: "gemini_model", modelPlaceholder: "gemini-2.5-flash" },
  { value: "groq", label: "Groq", key: "groq_api_key", model: "groq_model", modelPlaceholder: "openai/gpt-oss-120b" },
  { value: "openrouter", label: "OpenRouter", key: "openrouter_api_key", model: "openrouter_model", modelPlaceholder: "openai/gpt-oss-120b" },
] as const;

function Toggle({ checked, onChange, label, hint, recommended }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string; recommended?: boolean;
}) {
  return (
    <button type="button" onClick={() => onChange(!checked)}
      className="w-full flex items-start gap-3 p-3 rounded-lg border border-slate-200 hover:border-slate-300 bg-white text-left">
      <span className={`mt-0.5 w-8 h-[18px] rounded-full relative transition-colors shrink-0
        ${checked ? "bg-indigo-600" : "bg-slate-200"}`}>
        <span className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all
          ${checked ? "left-[18px]" : "left-[2px]"}`} />
      </span>
      <span className="min-w-0">
        <span className="text-sm font-medium text-slate-800 flex items-center gap-2">
          {label}
          {recommended && <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-px rounded">Recommended</span>}
        </span>
        {hint && <span className="block text-xs text-slate-500 mt-0.5">{hint}</span>}
      </span>
    </button>
  );
}

/* ── Step 1: Resume ───────────────────────────────────────────────────────── */

function CVUploadZone({ onParsed }: { onParsed: (p: CVProfile) => void }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  async function process(file: File) {
    if (!file.type.includes("pdf")) { setError("Please upload a PDF file"); return; }
    setError(""); setUploading(true);
    const fd = new FormData();
    fd.append("cv_file", file);
    try {
      const r = await api.post<CVProfile>("/api/cv/parse", fd, {
        headers: { "Content-Type": "multipart/form-data" }, timeout: 120_000,
      });
      onParsed(r.data);
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "CV parsing failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <label
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) process(f); }}
        className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-lg
          py-8 px-6 cursor-pointer transition-colors ${
          uploading ? "border-indigo-300 bg-indigo-50/50" :
          dragOver  ? "border-indigo-400 bg-indigo-50/50" :
                      "border-slate-200 bg-slate-50 hover:border-indigo-300"
        }`}
      >
        {uploading ? (
          <>
            <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
            <p className="text-sm font-medium text-indigo-700">Parsing resume with AI…</p>
            <p className="text-xs text-indigo-400">Usually 15–30 seconds</p>
          </>
        ) : (
          <>
            <Upload className="w-5 h-5 text-slate-400" />
            <p className="text-sm font-medium text-slate-700">
              Drop your resume here, or <span className="text-indigo-600">browse</span>
            </p>
            <p className="text-xs text-slate-400">PDF only · parsed locally via your configured AI provider</p>
          </>
        )}
        <input type="file" accept=".pdf" className="hidden" disabled={uploading}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) process(f); }} />
      </label>
      {error && (
        <p className="flex items-center gap-1.5 mt-2 text-xs text-red-600">
          <AlertCircle className="w-3.5 h-3.5" />{error}
        </p>
      )}
    </div>
  );
}

function ParsedResumePreview({ profile }: { profile: CVProfile }) {
  return (
    <div className="mt-4 border border-emerald-200 bg-emerald-50/60 rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
        <span className="text-sm font-semibold text-emerald-800">Resume parsed</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        {[
          { icon: User, val: profile.name },
          { icon: Mail, val: profile.email },
          { icon: Phone, val: profile.phone },
          { icon: Star, val: profile.experience_years ? `${profile.experience_years} years experience` : "" },
          { icon: Briefcase, val: profile.job_titles.slice(0, 2).join(", ") },
        ].filter((i) => i.val).map(({ icon: Icon, val }) => (
          <div key={val} className="flex items-center gap-1.5 text-slate-600 min-w-0">
            <Icon className="w-3 h-3 text-slate-400 shrink-0" />
            <span className="truncate">{val}</span>
          </div>
        ))}
      </div>
      {profile.skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {profile.skills.slice(0, 10).map((s) => (
            <span key={s} className="px-1.5 py-0.5 bg-white border border-emerald-200 text-emerald-700 text-[11px] rounded">{s}</span>
          ))}
          {profile.skills.length > 10 && (
            <span className="px-1.5 py-0.5 bg-white border border-slate-200 text-slate-500 text-[11px] rounded">
              +{profile.skills.length - 10} more
            </span>
          )}
        </div>
      )}
      {profile.summary && <p className="text-xs text-slate-500 line-clamp-2">{profile.summary}</p>}
    </div>
  );
}

/* ── Stepper ─────────────────────────────────────────────────────────────── */

const STEPS = [
  { n: 1, label: "Resume", icon: FileText },
  { n: 2, label: "Job preferences", icon: Sliders },
  { n: 3, label: "Credentials & launch", icon: ShieldCheck },
];

function Stepper({ step, goto, maxReached }: { step: number; goto: (n: number) => void; maxReached: number }) {
  return (
    <div className="flex items-center gap-2">
      {STEPS.map(({ n, label, icon: Icon }, i) => {
        const active = step === n;
        const done = n < step;
        const reachable = n <= maxReached;
        return (
          <div key={n} className="flex items-center gap-2">
            {i > 0 && <div className={`w-8 h-px ${done || active ? "bg-indigo-300" : "bg-slate-200"}`} />}
            <button type="button" disabled={!reachable} onClick={() => reachable && goto(n)}
              className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors
                ${active ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                : done ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-slate-200 bg-white text-slate-400"}
                ${reachable && !active ? "hover:border-slate-300" : ""}`}>
              {done ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Icon className="w-3.5 h-3.5" />}
              <span>{n}. {label}</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────────────── */

export default function SetupPage() {
  const navigate = useNavigate();
  const reset = useSessionStore((s) => s.reset);
  const setRunning = useSessionStore((s) => s.setRunning);

  const [step, setStep] = useState(1);
  const [maxReached, setMaxReached] = useState(1);
  const [profile, setProfile] = useState<CVProfile | null>(null);
  const [startErr, setStartErr] = useState("");
  const [starting, setStarting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const [keywordsText, setKeywordsText] = useState("");
  const [prefs, setPrefs] = useState<Omit<SessionStartRequest, "keywords">>({
    platform: "naukri",
    mode: "search_and_apply",
    location: "gurugram",
    job_target: 5,
    confidence_threshold: 75,
    easy_apply_only: true,            // default ON
    include_external_review: true,    // default ON
    outreach_mode: "draft_only",      // default recommended
    hide_previously_skipped: true,
    auto_ignore_skipped: true,
    date_posted_filter: "any",
  });

  const [cfg, setCfg] = useState({
    naukri_email: "", naukri_password: "",
    linkedin_email: "", linkedin_password: "",
    ai_provider: "groq" as AppConfig["ai_provider"],
    openai_api_key: "", openai_model: "gpt-4o-mini",
    gemini_api_key: "", gemini_model: "gemini-2.5-flash",
    groq_api_key: "", groq_model: "openai/gpt-oss-120b",
    openrouter_api_key: "", openrouter_model: "openai/gpt-oss-120b",
    openrouter_base_url: "https://openrouter.ai/api/v1",
    confidence_threshold: 75, max_jobs_per_hour: 30, max_jobs_per_day: 150,
    smtp_host: "", smtp_port: 587, smtp_username: "", smtp_password: "", smtp_from: "",
    hide_previously_skipped: true,
    auto_ignore_skipped: true,
    date_posted_filter: "any",
  });
  const [smtpTest, setSmtpTest] = useState<{ ok: boolean; message: string } | null>(null);
  const [smtpTesting, setSmtpTesting] = useState(false);

  useEffect(() => {
    api.get<CVProfile>("/api/cv/profile").then((r) => {
      setProfile(r.data);
      setKeywordsText((t) => t || (r.data.job_titles ?? []).slice(0, 3).join(", "));
    }).catch(() => {});
    api.get<AppConfig>("/api/config").then((r) => {
      const d = r.data;
      const provider = String(d.ai_provider || "groq");
      setCfg((c) => ({
        ...c,
        naukri_email: d.naukri_email || "", naukri_password: d.naukri_password || "",
        linkedin_email: d.linkedin_email || "", linkedin_password: d.linkedin_password || "",
        ai_provider: (provider === "grok" ? "groq" : provider === "azure" ? "openai" : provider) as AppConfig["ai_provider"],
        openai_api_key: d.openai_api_key || "", openai_model: d.openai_model || "gpt-4o-mini",
        gemini_api_key: d.gemini_api_key || "", gemini_model: d.gemini_model || "gemini-2.5-flash",
        groq_api_key: d.groq_api_key || "", groq_model: d.groq_model || "openai/gpt-oss-120b",
        openrouter_api_key: d.openrouter_api_key || "", openrouter_model: d.openrouter_model || "openai/gpt-oss-120b",
        openrouter_base_url: d.openrouter_base_url || "https://openrouter.ai/api/v1",
        confidence_threshold: d.confidence_threshold, max_jobs_per_hour: d.max_jobs_per_hour,
        max_jobs_per_day: d.max_jobs_per_day ?? 150,
        smtp_host: d.smtp_host || "", smtp_port: d.smtp_port ?? 587,
        smtp_username: d.smtp_username || "", smtp_password: d.smtp_password || "",
        smtp_from: d.smtp_from || "",
        hide_previously_skipped: d.hide_previously_skipped ?? true,
        auto_ignore_skipped: d.auto_ignore_skipped ?? true,
        date_posted_filter: d.date_posted_filter ?? "any",
      }));
      setPrefs((p) => ({
        ...p,
        confidence_threshold: d.confidence_threshold ?? p.confidence_threshold,
        easy_apply_only: d.easy_apply_only ?? true,
        include_external_review: d.include_external_review ?? true,
        outreach_mode: (d.outreach_mode as OutreachMode) ?? "draft_only",
        hide_previously_skipped: d.hide_previously_skipped ?? true,
        auto_ignore_skipped: d.auto_ignore_skipped ?? true,
        date_posted_filter: d.date_posted_filter ?? "any",
      }));
    }).catch(() => {});
  }, []);

  function next() {
    const n = Math.min(step + 1, 3);
    setStep(n);
    setMaxReached((m) => Math.max(m, n));
  }

  function buildConfigPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      ...cfg,
      easy_apply_only: prefs.easy_apply_only,
      include_external_review: prefs.include_external_review,
      outreach_mode: prefs.outreach_mode,
      confidence_threshold: prefs.confidence_threshold,
      hide_previously_skipped: prefs.hide_previously_skipped,
      auto_ignore_skipped: prefs.auto_ignore_skipped,
      date_posted_filter: prefs.date_posted_filter,
    };
    SECRET_FIELDS.forEach((k) => {
      if (!payload[k] || payload[k] === SECRET_MASK) delete payload[k];
    });
    return payload;
  }

  async function saveConfig() {
    setSaving(true);
    try {
      await api.put("/api/config", buildConfigPayload());
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTesting(true); setTestResult(null);
    try {
      const payload: Record<string, unknown> = { ...cfg };
      SECRET_FIELDS.forEach((k) => { if (!payload[k]) delete payload[k]; });
      const r = await api.post<{ ok: boolean; provider: string; model: string; output: string }>(
        "/api/config/test", payload, { timeout: 60_000 });
      setTestResult({ ok: true, message: `${r.data.provider} / ${r.data.model}: ${r.data.output || "Connection ok"}` });
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      const provider = detail?.provider ? `${detail.provider}${detail.model ? ` / ${detail.model}` : ""}: ` : "";
      const error = typeof detail === "string" ? detail : detail?.error;
      setTestResult({ ok: false, message: `${provider}${error || e.message || "Connection test failed"}` });
    } finally {
      setTesting(false);
    }
  }

  async function launch() {
    setStartErr(""); setStarting(true);
    try {
      await api.put("/api/config", buildConfigPayload());
      const keywords = keywordsText.split(",").map((k) => k.trim()).filter(Boolean);
      const finalKeywords = keywords.length ? keywords : (profile?.job_titles ?? ["Software Engineer"]);
      const r = await api.post<{ session_id: number }>("/api/session/start", { ...prefs, keywords: finalKeywords });
      reset();
      setRunning(true, r.data.session_id);
      navigate("/dashboard");
    } catch (e: any) {
      setStartErr(e.response?.data?.detail ?? e.message);
    } finally {
      setStarting(false);
    }
  }

  async function sendTestEmail() {
    setSmtpTesting(true); setSmtpTest(null);
    try {
      const overrides: Record<string, unknown> = {
        host: cfg.smtp_host, port: cfg.smtp_port,
        username: cfg.smtp_username, from_address: cfg.smtp_from,
      };
      if (cfg.smtp_password && cfg.smtp_password !== SECRET_MASK) overrides.password = cfg.smtp_password;
      const r = await api.post<{ ok: boolean; sent_to: string }>("/api/outreach/smtp/test", overrides, { timeout: 45_000 });
      setSmtpTest({ ok: true, message: `Test email sent to ${r.data.sent_to} — check your inbox.` });
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      setSmtpTest({ ok: false, message: typeof detail === "string" ? detail : e.message });
    } finally {
      setSmtpTesting(false);
    }
  }

  const activeProvider = AI_PROVIDER_OPTIONS.find((p) => p.value === cfg.ai_provider) ?? AI_PROVIDER_OPTIONS[0];
  const activeKey = (cfg as any)[activeProvider.key] || "";
  const activeModel = (cfg as any)[activeProvider.model] || "";

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-5">
        <h1 className="text-xl font-bold text-slate-900">Setup</h1>
        <p className="text-slate-500 text-sm mt-0.5">Three steps: resume → preferences → credentials &amp; launch</p>
      </div>

      <div className="mb-5"><Stepper step={step} goto={setStep} maxReached={maxReached} /></div>

      {/* ── Step 1: Resume ── */}
      {step === 1 && (
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-1">Upload your resume</h2>
          <p className="text-xs text-slate-500 mb-4">AI extracts your skills, titles and experience to score jobs against. Stored locally only.</p>
          <CVUploadZone onParsed={setProfile} />
          {profile && <ParsedResumePreview profile={profile} />}
          <div className="flex items-center justify-between mt-5">
            <LocalOnlyNote text="Your resume stays on this machine — it is only sent to your own AI provider for parsing." />
            <button onClick={next}
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg">
              {profile ? "Continue" : "Skip for now"} <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </Card>
      )}

      {/* ── Step 2: Job preferences ── */}
      {step === 2 && (
        <Card className="p-5 space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-800 mb-1">Job preferences</h2>
            <p className="text-xs text-slate-500">Where to search and how cautious to be.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Platform</Label>
              <div className="grid grid-cols-3 gap-1.5">
                {(["naukri", "linkedin", "both"] as const).map((p) => (
                  <button key={p} type="button" onClick={() => setPrefs({ ...prefs, platform: p })}
                    className={`py-1.5 rounded-lg border text-xs font-medium capitalize transition-colors
                      ${prefs.platform === p ? "bg-indigo-600 text-white border-indigo-600" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label>Mode</Label>
              <div className="grid grid-cols-2 gap-1.5">
                {[{ v: "search_and_apply", l: "Search & Apply" }, { v: "search", l: "Search only" }].map(({ v, l }) => (
                  <button key={v} type="button" onClick={() => setPrefs({ ...prefs, mode: v as any })}
                    className={`py-1.5 rounded-lg border text-xs font-medium transition-colors
                      ${prefs.mode === v ? "bg-indigo-600 text-white border-indigo-600" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
            <div className="col-span-2">
              <Label>Target job titles / keywords</Label>
              <input value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)}
                placeholder="QA Engineer, SDET, Automation Engineer" className={inputCls} />
              <p className="mt-1 text-[11px] text-slate-400">
                Comma-separated. Only these are searched; unrelated titles are skipped as "title mismatch" before scoring.
              </p>
            </div>
            <div>
              <Label>Location</Label>
              <input value={prefs.location} onChange={(e) => setPrefs({ ...prefs, location: e.target.value })}
                placeholder="gurugram" className={inputCls} />
            </div>
            <div>
              <Label>Date posted</Label>
              <select value={prefs.date_posted_filter}
                onChange={(e) => setPrefs({ ...prefs, date_posted_filter: e.target.value as any })}
                className={inputCls}>
                <option value="any">Any time</option>
                <option value="24h">Past 24 hours</option>
                <option value="3d">Past 3 days</option>
                <option value="7d">Past 7 days</option>
                <option value="14d">Past 14 days</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3 col-span-2">
              <div>
                <Label>Target jobs</Label>
                <input type="number" min={1} max={100} value={prefs.job_target}
                  onChange={(e) => setPrefs({ ...prefs, job_target: +e.target.value })} className={inputCls} />
              </div>
              <div>
                <Label>Min score</Label>
                <input type="number" min={0} max={100} value={prefs.confidence_threshold}
                  onChange={(e) => setPrefs({ ...prefs, confidence_threshold: +e.target.value })} className={inputCls} />
              </div>
            </div>
          </div>

          <div className="space-y-2 pt-1">
            <Toggle checked={prefs.easy_apply_only} recommended
              onChange={(v) => setPrefs({ ...prefs, easy_apply_only: v })}
              label="Easy Apply only"
              hint="LinkedIn: platform Easy Apply filter. Naukri: internal apply / chatbot flows only. External company sites are never auto-driven." />
            <Toggle checked={prefs.include_external_review} recommended
              onChange={(v) => setPrefs({ ...prefs, include_external_review: v })}
              label="Save external company-site jobs automatically"
              hint="Jobs that apply on a company website are saved with their link — no action needed, the session keeps moving. Turn off to skip them instead." />
            <Toggle checked={prefs.hide_previously_skipped} recommended
              onChange={(v) => setPrefs({ ...prefs, hide_previously_skipped: v })}
              label="Hide jobs skipped before"
              hint="Repeated jobs from the ignored sheet are skipped before details, scoring, or applying, so they do not keep filling the dashboard." />
            <Toggle checked={prefs.auto_ignore_skipped} recommended
              onChange={(v) => setPrefs({ ...prefs, auto_ignore_skipped: v })}
              label="Add skipped jobs to ignore sheet"
              hint="Stable skips like title mismatch, AI skip, low score, duplicate company, unsupported flow, or external site are remembered locally." />
          </div>

          <div className="flex items-center justify-between pt-1">
            <button onClick={() => setStep(1)}
              className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 hover:border-slate-300 text-slate-600 text-sm font-medium rounded-lg">
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
            <button onClick={next}
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg">
              Continue <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </Card>
      )}

      {/* ── Step 3: Credentials, AI provider, outreach, launch ── */}
      {step === 3 && (
        <div className="space-y-4">
          <Card className="p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-800 mb-1">Platform credentials</h2>
                <p className="text-xs text-slate-500">Used only by your local browser session to log in.</p>
              </div>
              <LocalOnlyNote />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Naukri Email", k: "naukri_email", type: "email" },
                { label: "Naukri Password", k: "naukri_password", type: "password" },
                { label: "LinkedIn Email", k: "linkedin_email", type: "email" },
                { label: "LinkedIn Password", k: "linkedin_password", type: "password" },
              ].map(({ label, k, type }) => (
                <div key={k}>
                  <Label>{label}</Label>
                  <input type={type} value={(cfg as any)[k]} placeholder={type === "password" ? "••••••••" : ""}
                    onFocus={() => { if (type === "password" && (cfg as any)[k] === SECRET_MASK) setCfg({ ...cfg, [k]: "" }); }}
                    onChange={(e) => setCfg({ ...cfg, [k]: e.target.value })} className={inputCls} />
                  {type === "password" && (cfg as any)[k] === SECRET_MASK && (
                    <p className="mt-1 text-[11px] text-emerald-600">Saved locally. Paste a new password only to replace it.</p>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-800 mb-1">AI provider</h2>
                <p className="text-xs text-slate-500">Scores jobs against your resume and answers apply-form questions.</p>
              </div>
              <LocalOnlyNote text="API keys are stored locally on this machine only." />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>Provider</Label>
                <select value={cfg.ai_provider}
                  onChange={(e) => { setTestResult(null); setCfg({ ...cfg, ai_provider: e.target.value as AppConfig["ai_provider"] }); }}
                  className={inputCls}>
                  {AI_PROVIDER_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              <div>
                <Label>API Key</Label>
                <div className="relative">
                  <Key className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                  <input type="password" value={activeKey} placeholder="Paste key"
                    onFocus={() => { if (activeKey === SECRET_MASK) setCfg({ ...cfg, [activeProvider.key]: "" }); }}
                    onChange={(e) => setCfg({ ...cfg, [activeProvider.key]: e.target.value })}
                    className={`${inputCls} pl-8`} />
                </div>
              </div>
              <div>
                <Label>Model</Label>
                <div className="relative">
                  <Cpu className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                  <input type="text" value={activeModel} placeholder={activeProvider.modelPlaceholder}
                    onChange={(e) => setCfg({ ...cfg, [activeProvider.model]: e.target.value })}
                    className={`${inputCls} pl-8`} />
                </div>
              </div>
            </div>
            {testResult && (
              <p className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${
                testResult.ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-600"}`}>
                {testResult.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                <span>{testResult.message}</span>
              </p>
            )}
            <div className="flex gap-2">
              <button onClick={testConnection} disabled={testing}
                className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 hover:border-slate-300 disabled:opacity-50 text-slate-700 text-xs font-semibold rounded-lg">
                {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Cpu className="w-3.5 h-3.5" />}
                {testing ? "Testing…" : "Test connection"}
              </button>
              <button onClick={saveConfig} disabled={saving}
                className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 hover:border-slate-300 disabled:opacity-50 text-slate-700 text-xs font-semibold rounded-lg">
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                {saved ? "Saved ✓" : saving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </Card>

          <Card className="p-5 space-y-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-800 mb-1">Recruiter email outreach</h2>
              <p className="text-xs text-slate-500">
                For external jobs, recruiter/HR emails are discovered only from visible public job content
                (job description, recruiter cards, mailto links). Nothing is ever sent automatically.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {([
                { v: "off", l: "Off", hint: "No drafts" },
                { v: "draft_only", l: "Draft only", hint: "Recommended" },
                { v: "send_after_approval", l: "Send after approval", hint: "Via your SMTP" },
              ] as const).map(({ v, l, hint }) => (
                <button key={v} type="button" onClick={() => setPrefs({ ...prefs, outreach_mode: v })}
                  className={`py-2 px-2 rounded-lg border text-left transition-colors
                    ${prefs.outreach_mode === v ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300"}`}>
                  <span className={`block text-xs font-semibold ${prefs.outreach_mode === v ? "text-indigo-700" : "text-slate-700"}`}>{l}</span>
                  <span className="block text-[11px] text-slate-400 mt-0.5">{hint}</span>
                </button>
              ))}
            </div>

            {prefs.outreach_mode === "send_after_approval" && (
              <div className="border border-slate-200 rounded-lg p-3 space-y-3 bg-slate-50/50">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs font-semibold text-slate-700">SMTP settings (your own mailbox)</p>
                  <LocalOnlyNote text="Stored locally. Gmail needs an App Password." />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {([
                    { label: "SMTP host", k: "smtp_host", type: "text", ph: "smtp.gmail.com" },
                    { label: "Port", k: "smtp_port", type: "number", ph: "587" },
                    { label: "From address", k: "smtp_from", type: "email", ph: "you@gmail.com" },
                    { label: "Username", k: "smtp_username", type: "text", ph: "you@gmail.com" },
                    { label: "Password / app password", k: "smtp_password", type: "password", ph: "••••••••" },
                  ] as const).map(({ label, k, type, ph }) => (
                    <div key={k}>
                      <Label>{label}</Label>
                      <input type={type} value={(cfg as any)[k]} placeholder={ph}
                        onFocus={() => { if (type === "password" && (cfg as any)[k] === SECRET_MASK) setCfg({ ...cfg, [k]: "" }); }}
                        onChange={(e) => setCfg({ ...cfg, [k]: type === "number" ? +e.target.value : e.target.value })}
                        className={inputCls} />
                    </div>
                  ))}
                  <div className="flex items-end">
                    <button type="button" onClick={sendTestEmail} disabled={smtpTesting}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-300 bg-white hover:border-slate-400 disabled:opacity-50 text-slate-700 text-xs font-semibold rounded-lg">
                      {smtpTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
                      {smtpTesting ? "Sending…" : "Send test email"}
                    </button>
                  </div>
                </div>
                {smtpTest && (
                  <p className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${
                    smtpTest.ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-600"}`}>
                    {smtpTest.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                    <span>{smtpTest.message}</span>
                  </p>
                )}
                <p className="text-[11px] text-slate-400">
                  Sending still requires you to approve each draft individually in the Review Queue. Every send is logged.
                </p>
              </div>
            )}
          </Card>

          {startErr && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5 text-xs text-red-600">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{startErr}
            </div>
          )}

          <div className="flex items-center justify-between">
            <button onClick={() => setStep(2)}
              className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 hover:border-slate-300 text-slate-600 text-sm font-medium rounded-lg">
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
            <button onClick={launch} disabled={starting}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60
                         text-white font-semibold rounded-lg text-sm">
              {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {starting ? "Starting…" : "Launch session"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
