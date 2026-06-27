import { useRef, useState } from "react";
import { User, Settings as SettingsIcon, Sliders, Camera, AlertTriangle, Trash2, Loader2, CheckCircle2, ShieldCheck } from "lucide-react";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { useSessionStore } from "../store/sessionStore";
import SetupPage from "./SetupPage";
import JobPreferencesPage from "./JobPreferencesPage";

type Tab = "account" | "settings" | "preferences";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "account", label: "Account", icon: User },
  { id: "settings", label: "Settings", icon: SettingsIcon },
  { id: "preferences", label: "Job Preferences", icon: Sliders },
];

function AccountTab() {
  const email = useAuthStore((s) => s.email);
  const fullName = useAuthStore((s) => s.fullName);
  const avatar = useAuthStore((s) => s.avatar);
  const setAvatar = useAuthStore((s) => s.setAvatar);
  const setFullName = useAuthStore((s) => s.setFullName);
  const reset = useSessionStore((s) => s.reset);
  const fileRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState(fullName || "");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetDone, setResetDone] = useState<string | null>(null);
  const [resetError, setResetError] = useState("");

  function onPhotoPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { alert("Please pick an image under 2 MB."); return; }
    const reader = new FileReader();
    reader.onload = () => setAvatar(reader.result as string);
    reader.readAsDataURL(file);
  }

  const initials = (name || email || "LU").slice(0, 2).toUpperCase();

  async function handleReset() {
    setResetting(true);
    setResetError("");
    setResetDone(null);
    try {
      const r = await api.post<{ deleted: Record<string, number>; files_removed: number }>("/api/system/reset");
      const total = Object.values(r.data.deleted).reduce((a, b) => a + b, 0);
      reset(); // clear live dashboard state too
      setResetDone(`Cleared ${total} record(s) and ${r.data.files_removed} file(s). Credentials kept.`);
      setConfirmOpen(false);
    } catch (e: any) {
      setResetError(e.response?.data?.detail || e.message || "Reset failed");
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Identity card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div className="flex items-center gap-5">
          <div className="relative">
            {avatar ? (
              <img src={avatar} alt="Profile" className="w-20 h-20 rounded-full object-cover border border-slate-200" />
            ) : (
              <div className="w-20 h-20 rounded-full bg-indigo-500 flex items-center justify-center text-white text-2xl font-bold">
                {initials}
              </div>
            )}
            <button onClick={() => fileRef.current?.click()}
              className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-white border border-slate-200 shadow flex items-center justify-center hover:bg-slate-50"
              aria-label="Change photo">
              <Camera className="w-3.5 h-3.5 text-slate-600" />
            </button>
            <input ref={fileRef} type="file" accept="image/*" onChange={onPhotoPick} className="hidden" />
          </div>
          <div className="flex-1 min-w-0">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setFullName(name)}
              placeholder="Your name"
              className="text-lg font-bold text-slate-900 bg-transparent border-b border-transparent hover:border-slate-200 focus:border-indigo-400 focus:outline-none w-full"
            />
            <p className="text-sm text-slate-500 mt-1">{email || "Local account"}</p>
            {avatar && (
              <button onClick={() => setAvatar(null)} className="text-[11px] text-slate-400 hover:text-red-500 mt-1">
                Remove photo
              </button>
            )}
          </div>
        </div>
        <div className="mt-5 flex items-center gap-2 text-[12px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
          <ShieldCheck className="w-4 h-4 shrink-0" />
          Everything is stored locally on this machine — nothing is uploaded.
        </div>
      </div>

      {/* Danger zone */}
      <div className="bg-white border border-red-200 rounded-xl p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-bold text-red-700">Danger zone — hard reset</h3>
            <p className="text-[13px] text-slate-600 mt-1 leading-relaxed">
              Deletes all job-search data: sessions, applied/saved/skipped jobs, ignored jobs,
              email drafts, history, and your uploaded resume. Your credentials
              (AI keys, Naukri & LinkedIn logins) and preferences are <span className="font-semibold">kept</span>.
            </p>

            {resetDone && (
              <div className="mt-3 flex items-center gap-2 text-emerald-700 text-sm">
                <CheckCircle2 className="w-4 h-4" /> {resetDone}
              </div>
            )}
            {resetError && (
              <div className="mt-3 text-red-600 text-sm">{resetError}</div>
            )}

            {!confirmOpen ? (
              <button onClick={() => { setConfirmOpen(true); setResetDone(null); }}
                className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg">
                <Trash2 className="w-4 h-4" /> Hard reset job data
              </button>
            ) : (
              <div className="mt-4 flex items-center gap-2">
                <span className="text-sm text-slate-700">Are you sure? This can't be undone.</span>
                <button onClick={handleReset} disabled={resetting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white text-sm font-semibold rounded-lg">
                  {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  Yes, delete it
                </button>
                <button onClick={() => setConfirmOpen(false)} disabled={resetting}
                  className="px-3 py-1.5 border border-slate-200 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-50">
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const [tab, setTab] = useState<Tab>("account");

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Profile</h1>
        <p className="text-slate-500 text-sm mt-1">Your account, settings, and job preferences</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200 mb-6">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === id
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}>
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content. Settings/Preferences embed the existing pages. */}
      {tab === "account" && <AccountTab />}
      {tab === "settings" && <div className="-m-8"><SetupPage /></div>}
      {tab === "preferences" && <div className="-m-8"><JobPreferencesPage /></div>}
    </div>
  );
}
