import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, AlertCircle, ChevronDown, ChevronUp, Wand2 } from "lucide-react";
import { api } from "../api/client";
import type { AppConfig, CVProfile } from "../api/types";
import { Card, LocalOnlyNote } from "../components/ui";

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">{children}</label>;
}

const inputCls = `w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
  focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
  hover:border-slate-300 bg-white text-slate-900 placeholder-slate-400`;

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

export default function JobPreferencesPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [suggestingKeywords, setSuggestingKeywords] = useState(false);
  const [suggestError, setSuggestError] = useState("");

  const [prefs, setPrefs] = useState({
    platform: "naukri" as "naukri" | "linkedin" | "both",
    mode: "search_and_apply" as "search" | "search_and_apply",
    location: "gurugram",
    job_target: 5,
    confidence_threshold: 75,
    easy_apply_only: true,
    include_external_review: true,
    hide_previously_skipped: true,
    auto_ignore_skipped: true,
    date_posted_filter: "any" as "any" | "24h" | "3d" | "7d" | "14d",
  });

  const [platforms, setPlatforms] = useState({
    naukri: { enabled: true, expanded: false, email: "", password: "", search_mode: "selenium" as "selenium" | "api", cookie: "", nkparam: "", auto_capture: false },
    linkedin: { enabled: false, expanded: false, email: "", password: "" },
  });

  const [capturing, setCapturing] = useState(false);
  const [captureMsg, setCaptureMsg] = useState("");
  const [captureError, setCaptureError] = useState("");

  const SECRET_MASK = "***";

  useEffect(() => {
    async function fetchData() {
      try {
        const cfgRes = await api.get<AppConfig>("/api/config");
        const cfg = cfgRes.data;
        setPrefs({
          platform: cfg.platform || "naukri",
          mode: cfg.mode || "search_and_apply",
          location: cfg.location || "gurugram",
          job_target: cfg.job_target || 5,
          confidence_threshold: cfg.confidence_threshold || 75,
          easy_apply_only: cfg.easy_apply_only ?? true,
          include_external_review: cfg.include_external_review ?? true,
          hide_previously_skipped: cfg.hide_previously_skipped ?? true,
          auto_ignore_skipped: cfg.auto_ignore_skipped ?? true,
          date_posted_filter: cfg.date_posted_filter || "any",
        });
        setPlatforms({
          naukri: {
            enabled: cfg.platform === "naukri" || cfg.platform === "both",
            expanded: false,
            email: cfg.naukri_email || "",
            password: cfg.naukri_password || "",
            search_mode: (cfg.naukri_search_mode as "selenium" | "api") || "selenium",
            cookie: cfg.naukri_cookie || "",
            nkparam: cfg.naukri_nkparam || "",
            auto_capture: cfg.naukri_auto_capture ?? false,
          },
          linkedin: {
            enabled: cfg.platform === "linkedin" || cfg.platform === "both",
            expanded: false,
            email: cfg.linkedin_email || "",
            password: cfg.linkedin_password || "",
          },
        });
        setKeywordsText((cfg.keywords || []).join(", "));
      } catch (e) {
        console.error("Failed to fetch preferences:", e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  async function handleCaptureTokens() {
    setCapturing(true);
    setCaptureMsg("");
    setCaptureError("");
    try {
      const res = await api.post<{ ok: boolean; cookie_preview: string; nkparam_preview: string }>(
        "/api/naukri/capture-tokens"
      );
      // Backend saved + switched to API mode; reflect that locally with masked values.
      setPlatforms((p) => ({
        ...p,
        naukri: { ...p.naukri, search_mode: "api", cookie: SECRET_MASK, nkparam: SECRET_MASK },
      }));
      setCaptureMsg(`Captured ✓  cookie ${res.data.cookie_preview} · nkparam ${res.data.nkparam_preview}`);
    } catch (e: any) {
      console.error("Token capture failed:", e);
      const detail = e.response?.data?.detail;
      setCaptureError(
        typeof detail === "string" ? detail : detail ? String(detail) : "Token capture failed"
      );
    } finally {
      setCapturing(false);
    }
  }

  async function handleSuggestKeywords() {
    setSuggestingKeywords(true);
    setSuggestError("");
    try {
      const profileRes = await api.get<CVProfile>("/api/cv/profile");
      const profile = profileRes.data;

      const res = await api.post<{ keywords: string[] }>("/api/cv/suggest-keywords", {
        cv_text: profile.raw_text || `${profile.name}\n${profile.job_titles?.join(", ")}\n${profile.skills?.join(", ")}`,
      });

      const suggested = res.data.keywords;
      const combined = Array.from(new Set([...keywordsText.split(",").map(s => s.trim()).filter(Boolean), ...suggested]));
      setKeywordsText(combined.join(", "));
    } catch (e: any) {
      console.error("Failed to suggest keywords:", e);
      const detail = e.response?.data?.detail;
      setSuggestError(
        typeof detail === "string" ? detail
        : detail ? String(detail)
        : "Failed to suggest keywords"
      );
    } finally {
      setSuggestingKeywords(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      // Determine platform based on enabled platforms
      let platformValue: "naukri" | "linkedin" | "both" = "naukri";
      if (platforms.naukri.enabled && platforms.linkedin.enabled) {
        platformValue = "both";
      } else if (platforms.linkedin.enabled) {
        platformValue = "linkedin";
      } else if (platforms.naukri.enabled) {
        platformValue = "naukri";
      }

      const payload = {
        platform: platformValue,
        mode: prefs.mode,
        keywords: keywordsText.split(",").map((s) => s.trim()).filter(Boolean),
        location: prefs.location,
        job_target: prefs.job_target,
        confidence_threshold: prefs.confidence_threshold,
        easy_apply_only: prefs.easy_apply_only,
        include_external_review: prefs.include_external_review,
        hide_previously_skipped: prefs.hide_previously_skipped,
        auto_ignore_skipped: prefs.auto_ignore_skipped,
        date_posted_filter: prefs.date_posted_filter,
        naukri_email: platforms.naukri.email || undefined,
        naukri_password: platforms.naukri.password === SECRET_MASK ? undefined : platforms.naukri.password || undefined,
        naukri_search_mode: platforms.naukri.search_mode,
        naukri_cookie: platforms.naukri.cookie === SECRET_MASK ? undefined : platforms.naukri.cookie || undefined,
        naukri_nkparam: platforms.naukri.nkparam === SECRET_MASK ? undefined : platforms.naukri.nkparam || undefined,
        naukri_auto_capture: platforms.naukri.auto_capture,
        linkedin_email: platforms.linkedin.email || undefined,
        linkedin_password: platforms.linkedin.password === SECRET_MASK ? undefined : platforms.linkedin.password || undefined,
      };
      console.log("Saving preferences:", payload);
      const response = await api.put("/api/config", payload);
      console.log("Save response:", response.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      console.error("Failed to save preferences:", e);
      console.error("Error response:", e.response?.data);
      const detail = e.response?.data?.detail;
      if (typeof detail === 'object') {
        setError(JSON.stringify(detail));
      } else {
        setError(detail || e.message || "Failed to save preferences");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-200 rounded w-1/3" />
          <div className="h-64 bg-slate-200 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Job Preferences</h1>
          <p className="text-slate-500 text-sm mt-0.5">Where to search and how cautious to be</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-sm font-semibold rounded-lg transition-colors"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          {saved ? "Saved ✓" : saving ? "Saving…" : "Save"}
        </button>
      </div>

      <Card className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-800 mb-1">Platform Selection</h2>
            <p className="text-xs text-slate-500">Enable platforms and configure credentials</p>
          </div>
          <LocalOnlyNote />
        </div>

        {/* Platform Cards */}
        <div className="space-y-3">
          {/* Naukri Platform Card */}
          <div className={`border rounded-lg overflow-hidden ${platforms.naukri.enabled ? "border-indigo-300 bg-indigo-50/30" : "border-slate-200 bg-white"}`}>
            <button
              type="button"
              onClick={() => {
                const newEnabled = !platforms.naukri.enabled;
                const newPlatform: "naukri" | "linkedin" | "both" = newEnabled 
                  ? (platforms.linkedin.enabled ? "both" : "naukri")
                  : (platforms.linkedin.enabled ? "linkedin" : "naukri");
                setPlatforms({
                  ...platforms,
                  naukri: { ...platforms.naukri, enabled: newEnabled, expanded: newEnabled },
                });
                setPrefs({
                  ...prefs,
                  platform: newPlatform,
                });
              }}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors
                  ${platforms.naukri.enabled ? "bg-indigo-600 border-indigo-600" : "border-slate-300 bg-white"}`}>
                  {platforms.naukri.enabled && <CheckCircle2 className="w-3 h-3 text-white" />}
                </div>
                <div className="text-left">
                  <span className="text-sm font-semibold text-slate-800">Naukri</span>
                  <p className="text-[11px] text-slate-500">India's leading job portal</p>
                </div>
              </div>
              {platforms.naukri.enabled && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPlatforms({ ...platforms, naukri: { ...platforms.naukri, expanded: !platforms.naukri.expanded } });
                  }}
                  className="p-1 hover:bg-slate-200 rounded transition-colors"
                >
                  {platforms.naukri.expanded ? <ChevronUp className="w-4 h-4 text-slate-600" /> : <ChevronDown className="w-4 h-4 text-slate-600" />}
                </button>
              )}
            </button>

            {/* Naukri Credentials Dropdown */}
            {platforms.naukri.enabled && platforms.naukri.expanded && (
              <div className="border-t border-slate-200 p-4 space-y-3 bg-white">
                <div>
                  <Label>Search Mode</Label>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    {([
                      { v: "selenium", l: "Selenium (Browser)", hint: "Default - uses browser automation" },
                      { v: "api", l: "API Mode", hint: "Faster - uses Naukri API directly" },
                    ] as const).map(({ v, l, hint }) => (
                      <button key={v} type="button" onClick={() => setPlatforms({ ...platforms, naukri: { ...platforms.naukri, search_mode: v } })}
                        className={`py-2 px-2 rounded-lg border text-left transition-colors
                          ${platforms.naukri.search_mode === v ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300"}`}>
                        <span className={`block text-xs font-semibold ${platforms.naukri.search_mode === v ? "text-indigo-700" : "text-slate-700"}`}>{l}</span>
                        <span className="block text-[11px] text-slate-400 mt-0.5">{hint}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* API mode auth tokens */}
                {platforms.naukri.search_mode === "api" && (
                  <div className="space-y-3 rounded-lg border border-indigo-200 bg-indigo-50/40 p-3">
                    {/* Auto-capture toggle */}
                    <button
                      type="button"
                      onClick={() => setPlatforms({ ...platforms, naukri: { ...platforms.naukri, auto_capture: !platforms.naukri.auto_capture } })}
                      className="w-full flex items-start gap-3 p-2 rounded-lg hover:bg-white/60 text-left transition-colors"
                    >
                      <span className={`mt-0.5 w-8 h-[18px] rounded-full relative transition-colors shrink-0
                        ${platforms.naukri.auto_capture ? "bg-indigo-600" : "bg-slate-300"}`}>
                        <span className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all
                          ${platforms.naukri.auto_capture ? "left-[18px]" : "left-[2px]"}`} />
                      </span>
                      <span className="min-w-0">
                        <span className="text-sm font-medium text-slate-800">Auto-detect tokens (recommended)</span>
                        <span className="block text-[11px] text-slate-500 mt-0.5">
                          Opens a real browser, runs your search, and grabs the cookie + nkparam for you — no DevTools copy-paste.
                        </span>
                      </span>
                    </button>

                    {platforms.naukri.auto_capture ? (
                      <div className="space-y-2">
                        <button
                          type="button"
                          onClick={handleCaptureTokens}
                          disabled={capturing}
                          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
                        >
                          {capturing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                          {capturing ? "Capturing… (a browser window will open)" : "Detect tokens now"}
                        </button>
                        <p className="text-[11px] text-slate-500 leading-relaxed">
                          A Chrome window opens and navigates to your Naukri search. Keep it open until it
                          closes itself. If a captcha appears, solve it in that window. Tokens expire after
                          a while — click again whenever search stops returning jobs.
                        </p>
                        {captureMsg && <p className="text-[11px] text-emerald-600">{captureMsg}</p>}
                        {captureError && <p className="text-[11px] text-red-600">{captureError}</p>}
                      </div>
                    ) : (
                      <>
                        <p className="text-[11px] text-slate-600 leading-relaxed">
                          Paste two values from a logged-in Naukri tab. Open{" "}
                          <span className="font-semibold">naukri.com</span>, run a job search, then in
                          DevTools → Network click the <span className="font-mono">search</span> request →
                          Headers, and copy the <span className="font-mono">cookie</span> and{" "}
                          <span className="font-mono">nkparam</span> values.
                        </p>
                        <div>
                          <Label>Cookie</Label>
                          <textarea
                            value={platforms.naukri.cookie}
                            onChange={(e) => setPlatforms({ ...platforms, naukri: { ...platforms.naukri, cookie: e.target.value } })}
                            onFocus={() => { if (platforms.naukri.cookie === SECRET_MASK) setPlatforms({ ...platforms, naukri: { ...platforms.naukri, cookie: "" } }); }}
                            placeholder="_t_ds=...; nauk_at=...; bm_sv=..."
                            rows={3}
                            className={`${inputCls} font-mono text-[11px] resize-y`}
                          />
                          {platforms.naukri.cookie === SECRET_MASK && (
                            <p className="mt-1 text-[11px] text-emerald-600">Saved locally. Paste a new value only to replace it.</p>
                          )}
                        </div>
                        <div>
                          <Label>nkparam</Label>
                          <textarea
                            value={platforms.naukri.nkparam}
                            onChange={(e) => setPlatforms({ ...platforms, naukri: { ...platforms.naukri, nkparam: e.target.value } })}
                            onFocus={() => { if (platforms.naukri.nkparam === SECRET_MASK) setPlatforms({ ...platforms, naukri: { ...platforms.naukri, nkparam: "" } }); }}
                            placeholder="bf4UNxrqZLus...=="
                            rows={2}
                            className={`${inputCls} font-mono text-[11px] resize-y`}
                          />
                          {platforms.naukri.nkparam === SECRET_MASK && (
                            <p className="mt-1 text-[11px] text-emerald-600">Saved locally. Paste a new value only to replace it.</p>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Email</Label>
                    <input
                      type="email"
                      value={platforms.naukri.email}
                      onChange={(e) => setPlatforms({ ...platforms, naukri: { ...platforms.naukri, email: e.target.value } })}
                      placeholder="your@email.com"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <Label>Password</Label>
                    <input
                      type="password"
                      value={platforms.naukri.password}
                      onChange={(e) => setPlatforms({ ...platforms, naukri: { ...platforms.naukri, password: e.target.value } })}
                      placeholder="••••••••"
                      onFocus={() => { if (platforms.naukri.password === SECRET_MASK) setPlatforms({ ...platforms, naukri: { ...platforms.naukri, password: "" } }); }}
                      className={inputCls}
                    />
                    {platforms.naukri.password === SECRET_MASK && (
                      <p className="mt-1 text-[11px] text-emerald-600">Saved locally. Paste a new password only to replace it.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* LinkedIn Platform Card */}
          <div className={`border rounded-lg overflow-hidden ${platforms.linkedin.enabled ? "border-indigo-300 bg-indigo-50/30" : "border-slate-200 bg-white"}`}>
            <button
              type="button"
              onClick={() => {
                const newEnabled = !platforms.linkedin.enabled;
                const newPlatform: "naukri" | "linkedin" | "both" = newEnabled 
                  ? (platforms.naukri.enabled ? "both" : "linkedin")
                  : (platforms.naukri.enabled ? "naukri" : "linkedin");
                setPlatforms({
                  ...platforms,
                  linkedin: { ...platforms.linkedin, enabled: newEnabled, expanded: newEnabled },
                });
                setPrefs({
                  ...prefs,
                  platform: newPlatform,
                });
              }}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors
                  ${platforms.linkedin.enabled ? "bg-indigo-600 border-indigo-600" : "border-slate-300 bg-white"}`}>
                  {platforms.linkedin.enabled && <CheckCircle2 className="w-3 h-3 text-white" />}
                </div>
                <div className="text-left">
                  <span className="text-sm font-semibold text-slate-800">LinkedIn</span>
                  <p className="text-[11px] text-slate-500">Professional networking & jobs</p>
                </div>
              </div>
              {platforms.linkedin.enabled && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPlatforms({ ...platforms, linkedin: { ...platforms.linkedin, expanded: !platforms.linkedin.expanded } });
                  }}
                  className="p-1 hover:bg-slate-200 rounded transition-colors"
                >
                  {platforms.linkedin.expanded ? <ChevronUp className="w-4 h-4 text-slate-600" /> : <ChevronDown className="w-4 h-4 text-slate-600" />}
                </button>
              )}
            </button>

            {/* LinkedIn Credentials Dropdown */}
            {platforms.linkedin.enabled && platforms.linkedin.expanded && (
              <div className="border-t border-slate-200 p-4 space-y-3 bg-white">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Email</Label>
                    <input
                      type="email"
                      value={platforms.linkedin.email}
                      onChange={(e) => setPlatforms({ ...platforms, linkedin: { ...platforms.linkedin, email: e.target.value } })}
                      placeholder="your@email.com"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <Label>Password</Label>
                    <input
                      type="password"
                      value={platforms.linkedin.password}
                      onChange={(e) => setPlatforms({ ...platforms, linkedin: { ...platforms.linkedin, password: e.target.value } })}
                      placeholder="••••••••"
                      onFocus={() => { if (platforms.linkedin.password === SECRET_MASK) setPlatforms({ ...platforms, linkedin: { ...platforms.linkedin, password: "" } }); }}
                      className={inputCls}
                    />
                    {platforms.linkedin.password === SECRET_MASK && (
                      <p className="mt-1 text-[11px] text-emerald-600">Saved locally. Paste a new password only to replace it.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
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
            <div className="flex items-center justify-between mb-1">
              <Label>Target job titles / keywords</Label>
              <button
                type="button"
                onClick={handleSuggestKeywords}
                disabled={suggestingKeywords}
                title="Auto-detect job titles from your resume using AI"
                className="flex items-center gap-1 px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {suggestingKeywords ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                {suggestingKeywords ? "Detecting..." : "Auto-detect"}
              </button>
            </div>
            <input value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="QA Engineer, SDET, Automation Engineer" className={inputCls} />
            <p className="mt-1 text-[11px] text-slate-400">
              Comma-separated. Only these are searched; unrelated titles are skipped as "title mismatch" before scoring.
            </p>
            {suggestError && (
              <p className="mt-2 text-[11px] text-red-600">{suggestError}</p>
            )}
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
      </Card>

      {saved && (
        <div className="flex items-center gap-2 text-emerald-600 text-sm">
          <CheckCircle2 className="w-4 h-4" />
          Preferences saved successfully
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}
    </div>
  );
}
