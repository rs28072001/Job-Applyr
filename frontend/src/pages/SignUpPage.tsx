import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Eye, EyeOff, Mail, Lock, User, Briefcase,
  Loader2, Check, Cpu,
} from "lucide-react";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";

/* ── Shared input atom ────────────────────────────────────────────────────── */
function Field({
  label, hint, icon: Icon, type = "text", value, onChange, placeholder, required, children,
}: {
  label: string; hint?: string; icon: React.ElementType; type?: string;
  value: string; onChange: (v: string) => void; placeholder?: string;
  required?: boolean; children?: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      <div className="relative">
        <Icon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
        {children ?? (
          <input
            type={type} value={value} onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder} required={required}
            className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl text-sm
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                       hover:border-gray-300 bg-gray-50 text-gray-900 placeholder-gray-400"
          />
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────────── */
export default function SignUpPage() {
  const navigate = useNavigate();
  const setAuth  = useAuthStore((s) => s.setAuth);

  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const [fullName, setFullName]       = useState("");
  const [email, setEmail]             = useState("");
  const [password, setPassword]       = useState("");
  const [confirmPw, setConfirmPw]     = useState("");
  const [showPw, setShowPw]           = useState(false);

  // Password strength
  const pwStrength = password.length === 0 ? -1
    : password.length < 6 ? 0
    : password.length < 10 ? 1
    : /[A-Z]/.test(password) && /[0-9]/.test(password) ? 3 : 2;
  const strengthLabel = ["Too short", "Weak", "Good", "Strong"][pwStrength + 1] ?? "";
  const strengthColor = ["", "bg-red-400", "bg-yellow-400", "bg-blue-400", "bg-emerald-500"][pwStrength + 1] ?? "";

  function validateForm() {
    if (!email || !password || !confirmPw) return "All fields are required";
    if (password.length < 6) return "Password must be at least 6 characters";
    if (password !== confirmPw) return "Passwords do not match";
    return "";
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const err = validateForm();
    if (err) { setError(err); return; }
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/api/auth/signup", {
        email, password, full_name: fullName,
      });
      setAuth(data.access_token, data.user_id, data.email, data.full_name);
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Left panel ── */}
      <div className="hidden lg:flex lg:w-5/12 xl:w-[45%] flex-col justify-between p-12
                      bg-gradient-to-br from-indigo-900 via-indigo-800 to-violet-900 relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-32 -left-32 w-80 h-80 bg-white/5 rounded-full blur-3xl" />
          <div className="absolute top-1/3 right-0 w-72 h-72 bg-violet-400/10 rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-1/4 w-96 h-64 bg-indigo-400/10 rounded-full blur-3xl" />
        </div>

        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 bg-white/10 backdrop-blur rounded-xl flex items-center justify-center">
            <Briefcase className="w-5 h-5 text-white" />
          </div>
          <span className="text-white font-bold text-xl tracking-tight">Smart Job Assistant</span>
        </div>

        <div className="relative">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur rounded-full px-4 py-2 mb-6">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-white text-sm font-medium">Setup takes under 2 minutes</span>
          </div>
          <h1 className="text-4xl xl:text-5xl font-extrabold text-white leading-tight mb-6">
            Start applying smarter today
          </h1>
          <p className="text-indigo-200 text-lg leading-relaxed">
            Create your free account, then add your preferred AI provider in settings when
            you are ready to parse CVs and score job matches.
          </p>

          <div className="mt-10 bg-white/10 backdrop-blur rounded-2xl p-5 border border-white/10">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 bg-emerald-400/20 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                <Cpu className="w-4 h-4 text-emerald-400" />
              </div>
              <div>
                <p className="text-white text-sm font-semibold mb-1">Bring your own AI key</p>
                <p className="text-indigo-200 text-xs leading-relaxed">
                  Add Azure OpenAI, OpenAI, Gemini, or Grok credentials after signup.
                  Your keys are stored locally in your own database.
                </p>
              </div>
            </div>
          </div>
        </div>

        <p className="relative text-indigo-400 text-xs">
          100% local. Your data stays on your machine.
        </p>
      </div>

      {/* ── Right panel ── */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white overflow-y-auto">
        <div className="w-full max-w-md py-4">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <Briefcase className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gray-900">Smart Job Assistant</span>
          </div>

          <div className="mb-6">
            <h2 className="text-3xl font-bold text-gray-900 mb-1">Create your account</h2>
            <p className="text-gray-500 text-sm">Free forever. No credit card required.</p>
          </div>

          <form onSubmit={submit} className="space-y-5">
              <Field label="Full name" icon={User} value={fullName} onChange={setFullName}
                placeholder="Bhawana Jangra" />

              <Field label="Email address" icon={Mail} value={email} onChange={setEmail}
                placeholder="you@example.com" required type="email" />

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Password <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 6 characters"
                    className="w-full pl-10 pr-10 py-3 border border-gray-200 rounded-xl text-sm
                               focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                               hover:border-gray-300 bg-gray-50 text-gray-900 placeholder-gray-400"
                  />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {password && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex gap-1 flex-1">
                      {[0, 1, 2, 3].map((i) => (
                        <div key={i} className={`h-1 flex-1 rounded-full transition-colors
                          ${i <= pwStrength ? strengthColor : "bg-gray-200"}`} />
                      ))}
                    </div>
                    <span className="text-xs text-gray-500">{strengthLabel}</span>
                  </div>
                )}
              </div>

              <Field label="Confirm password" icon={Lock} type="password"
                value={confirmPw} onChange={setConfirmPw} placeholder="Repeat your password" required />

              {error && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-100
                               rounded-xl px-4 py-3 text-sm">
                  ⚠ {error}
                </div>
              )}

              <button type="submit" disabled={loading}
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700
                           disabled:opacity-60 text-white font-semibold py-3 rounded-xl text-sm shadow-sm shadow-indigo-200">
                {loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Creating account...</>
                ) : (
                  <><Check className="w-4 h-4" /> Create account</>
                )}
              </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-indigo-600 hover:text-indigo-700">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
