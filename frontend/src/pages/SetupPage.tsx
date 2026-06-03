import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import {
  Upload, CheckCircle2, AlertCircle, Loader2, Play, Settings2,
  MapPin, Target, Sliders, User, Mail, Phone,
  Briefcase, Star, Save, ChevronDown,
} from "lucide-react";
import { api } from "../api/client";
import type { AppConfig, CVProfile, SessionStartRequest } from "../api/types";
import { useSessionStore } from "../store/sessionStore";

/* ── Shared atoms ──────────────────────────────────────────────────────────── */

function SectionCard({ title, description, icon: Icon, children }: {
  title: string; description?: string; icon: React.ElementType; children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4 text-indigo-600" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
        </div>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">
      {children}{required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
  );
}

const inputCls = `w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm
  focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
  hover:border-slate-300 bg-slate-50 text-slate-900 placeholder-slate-400`;

/* ── CV Upload Zone ──────────────────────────────────────────────────────── */

function CVUploadZone({ onParsed }: { onParsed: (p: CVProfile) => void }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError]         = useState("");
  const [dragOver, setDragOver]   = useState(false);

  async function process(file: File) {
    if (!file.type.includes("pdf")) { setError("Please upload a PDF file"); return; }
    setError(""); setUploading(true);
    const fd = new FormData();
    fd.append("cv_file", file);
    try {
      const r = await api.post<CVProfile>("/api/cv/parse", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120_000,
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
        className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl
          py-10 px-6 cursor-pointer transition-all duration-200 ${
          uploading ? "border-indigo-300 bg-indigo-50" :
          dragOver  ? "border-indigo-400 bg-indigo-50 scale-[1.01]" :
                      "border-slate-200 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/50"
        }`}
      >
        {uploading ? (
          <>
            <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
            </div>
            <p className="text-sm font-medium text-indigo-700">Parsing CV with AI…</p>
            <p className="text-xs text-indigo-500">This may take 15–30 seconds</p>
          </>
        ) : (
          <>
            <div className="w-12 h-12 bg-white border-2 border-slate-200 rounded-full flex items-center justify-center">
              <Upload className="w-5 h-5 text-slate-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-slate-700">
                Drop your CV here, or <span className="text-indigo-600">browse</span>
              </p>
              <p className="text-xs text-slate-400 mt-0.5">PDF only · AI will extract all fields automatically</p>
            </div>
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

/* ── Profile display card ───────────────────────────────────────────────── */

function ProfileCard({ profile }: { profile: CVProfile }) {
  return (
    <div className="mt-4 bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
        <span className="text-sm font-semibold text-emerald-800">CV parsed successfully</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        {[
          { icon: User,     val: profile.name },
          { icon: Mail,     val: profile.email },
          { icon: Phone,    val: profile.phone },
          { icon: Star,     val: `${profile.experience_years} years experience` },
          { icon: Briefcase,val: profile.job_titles.slice(0,2).join(", ") },
        ].filter(i => i.val).map(({ icon: Icon, val }) => (
          <div key={val} className="flex items-center gap-1.5 text-slate-600">
            <Icon className="w-3 h-3 text-slate-400 shrink-0" />
            <span className="truncate">{val}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {profile.skills.slice(0, 8).map((s) => (
          <span key={s} className="px-2 py-0.5 bg-white border border-emerald-200 text-emerald-700 text-xs rounded-full">
            {s}
          </span>
        ))}
        {profile.skills.length > 8 && (
          <span className="px-2 py-0.5 bg-white border border-slate-200 text-slate-500 text-xs rounded-full">
            +{profile.skills.length - 8} more
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Settings accordion ─────────────────────────────────────────────────── */

function SettingsAccordion() {
  const [open, setOpen]     = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]   = useState(false);
  const [cfg, setCfg]       = useState({ naukri_email:"", naukri_password:"",
                                          linkedin_email:"", linkedin_password:"",
                                          confidence_threshold:75, max_jobs_per_hour:30 });

  useEffect(() => {
    if (!open) return;
    api.get<AppConfig>("/api/config").then((r) => {
      setCfg({
        naukri_email: r.data.naukri_email || "",
        naukri_password: r.data.naukri_password === "***" ? "" : (r.data.naukri_password || ""),
        linkedin_email: r.data.linkedin_email || "",
        linkedin_password: r.data.linkedin_password === "***" ? "" : (r.data.linkedin_password || ""),
        confidence_threshold: r.data.confidence_threshold,
        max_jobs_per_hour: r.data.max_jobs_per_hour,
      });
    });
  }, [open]);

  async function save() {
    setSaving(true);
    await api.put("/api/config", cfg);
    setSaving(false); setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-6 py-4 hover:bg-slate-50 transition-colors">
        <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center shrink-0">
          <Settings2 className="w-4 h-4 text-slate-600" />
        </div>
        <div className="flex-1 text-left">
          <p className="text-sm font-semibold text-slate-900">Platform Credentials & Settings</p>
          <p className="text-xs text-slate-500 mt-0.5">Naukri, LinkedIn, rate limits</p>
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="px-6 py-5 border-t border-slate-100 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            {[
              { label:"Naukri Email",     k:"naukri_email",    type:"email" },
              { label:"Naukri Password",  k:"naukri_password", type:"password" },
              { label:"LinkedIn Email",   k:"linkedin_email",  type:"email" },
              { label:"LinkedIn Password",k:"linkedin_password",type:"password"},
            ].map(({ label, k, type }) => (
              <div key={k}>
                <Label>{label}</Label>
                <input type={type} value={(cfg as any)[k]} placeholder={type === "password" ? "••••••••" : ""}
                  onChange={(e) => setCfg({ ...cfg, [k]: e.target.value })}
                  className={inputCls} />
              </div>
            ))}
            <div>
              <Label>Confidence Threshold</Label>
              <input type="number" min={0} max={100}
                value={cfg.confidence_threshold}
                onChange={(e) => setCfg({ ...cfg, confidence_threshold: +e.target.value })}
                className={inputCls} />
            </div>
            <div>
              <Label>Max Applications / Hour</Label>
              <input type="number" min={1} max={100}
                value={cfg.max_jobs_per_hour}
                onChange={(e) => setCfg({ ...cfg, max_jobs_per_hour: +e.target.value })}
                className={inputCls} />
            </div>
          </div>
          <button onClick={save} disabled={saving}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-700
                       disabled:opacity-50 text-white text-sm font-semibold rounded-xl">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            {saved ? "Saved ✓" : saving ? "Saving…" : "Save settings"}
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────────── */

export default function SetupPage() {
  const navigate  = useNavigate();
  const reset     = useSessionStore((s) => s.reset);
  const setRunning= useSessionStore((s) => s.setRunning);

  const [profile, setProfile]   = useState<CVProfile | null>(null);
  const [startErr, setStartErr] = useState("");

  const { register, handleSubmit, setValue } = useForm<SessionStartRequest>({
    defaultValues: { platform:"naukri", mode:"search_and_apply",
                     location:"gurugram", job_target:5, confidence_threshold:75, keywords:[] },
  });

  useEffect(() => {
    api.get<CVProfile>("/api/cv/profile").then((r) => setProfile(r.data)).catch(() => {});
    api.get<AppConfig>("/api/config").then((r) => setValue("confidence_threshold", r.data.confidence_threshold)).catch(() => {});
  }, [setValue]);

  async function onStart(data: SessionStartRequest) {
    setStartErr("");
    const keywords = profile?.job_titles ?? ["Software Engineer"];
    try {
      const r = await api.post<{ session_id: number }>("/api/session/start", { ...data, keywords });
      reset();
      setRunning(true, r.data.session_id);
      navigate("/dashboard");
    } catch (e: any) {
      setStartErr(e.response?.data?.detail ?? e.message);
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Setup</h1>
        <p className="text-slate-500 text-sm mt-1">Configure your CV, job preferences, and start your session</p>
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Left column: CV + Settings */}
        <div className="col-span-3 space-y-5">
          {/* CV Upload */}
          <SectionCard title="CV / Resume" description="Upload once — AI extracts all your info" icon={Upload}>
            <CVUploadZone onParsed={setProfile} />
            {profile && <ProfileCard profile={profile} />}
          </SectionCard>

          {/* Platform settings accordion */}
          <SettingsAccordion />
        </div>

        {/* Right column: Launch config */}
        <div className="col-span-2">
          <form onSubmit={handleSubmit(onStart)}>
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden sticky top-6">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2.5">
                <div className="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center">
                  <Play className="w-4 h-4 text-indigo-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">Launch Session</p>
                  <p className="text-xs text-slate-500">Configure and start</p>
                </div>
              </div>

              <div className="px-5 py-5 space-y-4">
                {/* Platform */}
                <div>
                  <Label>Platform</Label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {["naukri","linkedin","both"].map((p) => (
                      <label key={p} className="cursor-pointer">
                        <input type="radio" value={p} {...register("platform")} className="sr-only peer" />
                        <div className="text-center py-2 rounded-lg border border-slate-200 text-xs font-medium text-slate-600
                                        peer-checked:bg-indigo-600 peer-checked:text-white peer-checked:border-indigo-600
                                        hover:border-slate-300 capitalize">
                          {p}
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Mode */}
                <div>
                  <Label>Mode</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { v:"search_and_apply", l:"Search & Apply" },
                      { v:"search",           l:"Search Only" },
                    ].map(({ v, l }) => (
                      <label key={v} className="cursor-pointer">
                        <input type="radio" value={v} {...register("mode")} className="sr-only peer" />
                        <div className="text-center py-2 rounded-lg border border-slate-200 text-xs font-medium text-slate-600
                                        peer-checked:bg-indigo-600 peer-checked:text-white peer-checked:border-indigo-600
                                        hover:border-slate-300">
                          {l}
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Location */}
                <div>
                  <Label>Location</Label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                    <input {...register("location")} placeholder="gurugram" className={`${inputCls} pl-8`} />
                  </div>
                </div>

                {/* Target + Threshold */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Target jobs</Label>
                    <div className="relative">
                      <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                      <input type="number" min={1} max={100} {...register("job_target",{valueAsNumber:true})}
                        className={`${inputCls} pl-8`} />
                    </div>
                  </div>
                  <div>
                    <Label>Min score</Label>
                    <div className="relative">
                      <Sliders className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                      <input type="number" min={0} max={100} {...register("confidence_threshold",{valueAsNumber:true})}
                        className={`${inputCls} pl-8`} />
                    </div>
                  </div>
                </div>

                {startErr && (
                  <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2.5 text-xs text-red-600">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{startErr}
                  </div>
                )}

                <button type="submit"
                  className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700
                             text-white font-bold py-3 rounded-xl text-sm shadow-sm shadow-indigo-200 mt-1">
                  <Play className="w-4 h-4" /> Start Session
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
