import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { api } from "../api/client";
import type { AppConfig, CVProfile, SessionStartRequest } from "../api/types";
import { useSessionStore } from "../store/sessionStore";

// ── small helpers ──────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

const inp =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

// ── Wizard ────────────────────────────────────────────────────────────────────

function Wizard({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [, setForm] = useState<Partial<AppConfig>>({});
  const [saving, setSaving] = useState(false);

  async function saveAndNext(fields: Partial<AppConfig>, last = false) {
    setSaving(true);
    await api.put("/api/config", fields);
    setForm((f) => ({ ...f, ...fields }));
    setSaving(false);
    if (last) onDone();
    else setStep((s) => s + 1);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <h2 className="text-xl font-bold text-gray-900 mb-1">Welcome 👋</h2>
        <p className="text-sm text-gray-500 mb-6">
          Step {step + 1} / 3 — complete setup once, credentials are saved to the DB.
        </p>

        {step === 0 && (
          <LLMStep onNext={(v) => saveAndNext(v)} saving={saving} />
        )}
        {step === 1 && (
          <PlatformStep onNext={(v) => saveAndNext(v)} saving={saving} />
        )}
        {step === 2 && (
          <PrefsStep onNext={(v) => saveAndNext(v, true)} saving={saving} />
        )}
      </div>
    </div>
  );
}

function LLMStep({ onNext, saving }: { onNext: (v: Partial<AppConfig>) => void; saving: boolean }) {
  const { register, handleSubmit } = useForm<Pick<AppConfig, "azure_openai_endpoint" | "azure_openai_api_key" | "azure_deployment_name">>();
  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <Field label="Azure OpenAI Endpoint">
        <input {...register("azure_openai_endpoint", { required: true })} className={inp} placeholder="https://..." />
      </Field>
      <Field label="Azure OpenAI API Key">
        <input {...register("azure_openai_api_key", { required: true })} type="password" className={inp} />
      </Field>
      <Field label="Deployment / Model Name">
        <input {...register("azure_deployment_name")} className={inp} placeholder="gpt-4o-mini" />
      </Field>
      <button type="submit" disabled={saving}
        className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
        {saving ? "Saving…" : "Next →"}
      </button>
    </form>
  );
}

function PlatformStep({ onNext, saving }: { onNext: (v: Partial<AppConfig>) => void; saving: boolean }) {
  const { register, handleSubmit } = useForm<Pick<AppConfig, "naukri_email" | "naukri_password" | "linkedin_email" | "linkedin_password">>();
  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <p className="text-xs text-gray-500 bg-blue-50 rounded-lg px-3 py-2">
        Credentials are saved to a local SQLite DB and never leave your machine.
      </p>
      <Field label="Naukri Email"><input {...register("naukri_email")} className={inp} /></Field>
      <Field label="Naukri Password"><input {...register("naukri_password")} type="password" className={inp} /></Field>
      <Field label="LinkedIn Email"><input {...register("linkedin_email")} className={inp} /></Field>
      <Field label="LinkedIn Password"><input {...register("linkedin_password")} type="password" className={inp} /></Field>
      <button type="submit" disabled={saving}
        className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
        {saving ? "Saving…" : "Next →"}
      </button>
    </form>
  );
}

function PrefsStep({ onNext, saving }: { onNext: (v: Partial<AppConfig>) => void; saving: boolean }) {
  const { register, handleSubmit } = useForm<Pick<AppConfig, "confidence_threshold" | "max_jobs_per_hour" | "max_jobs_per_day">>(
    { defaultValues: { confidence_threshold: 75, max_jobs_per_hour: 30, max_jobs_per_day: 150 } }
  );
  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <Field label="Confidence Threshold (0–100)">
        <input {...register("confidence_threshold", { valueAsNumber: true })} type="number" className={inp} />
      </Field>
      <Field label="Max Applications / Hour">
        <input {...register("max_jobs_per_hour", { valueAsNumber: true })} type="number" className={inp} />
      </Field>
      <Field label="Max Applications / Day">
        <input {...register("max_jobs_per_day", { valueAsNumber: true })} type="number" className={inp} />
      </Field>
      <button type="submit" disabled={saving}
        className="w-full bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
        {saving ? "Saving…" : "Finish Setup ✓"}
      </button>
    </form>
  );
}

// ── Main Setup page ────────────────────────────────────────────────────────────

export default function SetupPage() {
  const navigate  = useNavigate();
  const setRunning= useSessionStore((s) => s.setRunning);
  const reset     = useSessionStore((s) => s.reset);

  const [config, setConfig]     = useState<AppConfig | null>(null);
  const [profile, setProfile]   = useState<CVProfile | null>(null);
  const [showWizard, setWizard] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [startError, setStartError] = useState("");

  // Session start form
  const { register, handleSubmit, setValue } = useForm<SessionStartRequest>({
    defaultValues: {
      platform: "naukri",
      mode: "search_and_apply",
      location: "gurugram",
      job_target: 5,
      confidence_threshold: 75,
      keywords: [],
    },
  });

  useEffect(() => {
    api.get<AppConfig>("/api/config").then((r) => {
      setConfig(r.data);
      if (!r.data.is_configured) setWizard(true);
      setValue("confidence_threshold", r.data.confidence_threshold);
    });
    api.get<CVProfile>("/api/cv/profile")
      .then((r) => setProfile(r.data))
      .catch(() => {});
  }, [setValue]);

  async function handleCVUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("cv_file", file);
    try {
      const r = await api.post<CVProfile>("/api/cv/parse", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setProfile(r.data);
    } catch (err: any) {
      alert("CV parse failed: " + (err.response?.data?.detail ?? err.message));
    } finally {
      setUploading(false);
    }
  }

  async function onStart(data: SessionStartRequest) {
    setStartError("");
    // Use CV job_titles as keywords if not provided
    const keywords = profile?.job_titles ?? ["Software Engineer"];
    try {
      const r = await api.post<{ session_id: number }>("/api/session/start", {
        ...data,
        keywords,
      });
      reset();
      setRunning(true, r.data.session_id);
      navigate("/dashboard");
    } catch (err: any) {
      setStartError(err.response?.data?.detail ?? err.message);
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {showWizard && <Wizard onDone={() => { setWizard(false); window.location.reload(); }} />}

      <h1 className="text-2xl font-bold text-gray-900 mb-6">Setup</h1>

      {/* CV Upload */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
        <h2 className="font-semibold text-gray-800 mb-4">📄 CV / Resume</h2>

        <label className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg py-8 cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors">
          <span className="text-3xl mb-2">⬆️</span>
          <span className="text-sm text-gray-600">
            {uploading ? "Parsing CV…" : "Drop PDF here or click to upload"}
          </span>
          <input type="file" accept=".pdf" className="hidden" onChange={handleCVUpload} disabled={uploading} />
        </label>

        {profile && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4 text-sm space-y-1">
            <p><span className="font-medium">Name:</span> {profile.name}</p>
            <p><span className="font-medium">Email:</span> {profile.email}</p>
            <p><span className="font-medium">Phone:</span> {profile.phone}</p>
            <p><span className="font-medium">Experience:</span> {profile.experience_years} years</p>
            <p><span className="font-medium">Titles:</span> {profile.job_titles.join(", ")}</p>
            <p><span className="font-medium">Skills:</span> {profile.skills.slice(0, 10).join(", ")}</p>
          </div>
        )}
      </section>

      {/* Session Config */}
      <form onSubmit={handleSubmit(onStart)}>
        <section className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4">
          <h2 className="font-semibold text-gray-800">🎯 Job Search Preferences</h2>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Platform">
              <select {...register("platform")} className={inp}>
                <option value="naukri">Naukri</option>
                <option value="linkedin">LinkedIn</option>
                <option value="both">Both</option>
              </select>
            </Field>

            <Field label="Mode">
              <select {...register("mode")} className={inp}>
                <option value="search_and_apply">Search & Apply</option>
                <option value="search">Search Only</option>
              </select>
            </Field>

            <Field label="Location">
              <input {...register("location")} className={inp} placeholder="gurugram" />
            </Field>

            <Field label="Job Target">
              <input {...register("job_target", { valueAsNumber: true })} type="number" min={1} max={100} className={inp} />
            </Field>

            <Field label="Confidence Threshold">
              <input {...register("confidence_threshold", { valueAsNumber: true })} type="number" min={0} max={100} className={inp} />
            </Field>
          </div>

          {startError && (
            <p className="text-red-600 text-sm bg-red-50 rounded-lg px-3 py-2">{startError}</p>
          )}

          <button type="submit"
            className="w-full bg-blue-600 text-white py-3 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors mt-2">
            🚀 Start Session
          </button>
        </section>
      </form>

      {/* Config summary */}
      {config && (
        <div className="mt-4 text-xs text-gray-400 space-y-0.5 px-1">
          <p>Model: {config.azure_deployment_name} · Threshold: {config.confidence_threshold} · Max/hr: {config.max_jobs_per_hour}</p>
          <button onClick={() => setWizard(true)} className="text-blue-500 hover:underline">Edit credentials →</button>
        </div>
      )}
    </div>
  );
}
