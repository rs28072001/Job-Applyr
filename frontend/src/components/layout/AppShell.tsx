import { NavLink, Outlet } from "react-router-dom";
import { Ban, Briefcase, Settings, LayoutDashboard, History, Inbox, Sliders, FileText } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useSessionStore } from "../../store/sessionStore";
import ThemeToggle from "../ThemeToggle";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/setup", label: "Setup", icon: Settings },
  { to: "/preferences", label: "Job Preferences", icon: Sliders },
  { to: "/resume", label: "Resume", icon: FileText },
  { to: "/review", label: "Saved & Skipped", icon: Inbox },
  { to: "/ignored", label: "Ignored Jobs", icon: Ban },
  { to: "/history", label: "History", icon: History },
];

function Avatar({ name, email }: { name: string; email: string }) {
  const initials = name
    ? name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
    : email.slice(0, 2).toUpperCase() || "LU";
  return (
    <div className="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center
                    text-white text-[10px] font-bold shrink-0">
      {initials}
    </div>
  );
}

export default function AppShell() {
  const email = useAuthStore((s) => s.email) ?? "";
  const fullName = useAuthStore((s) => s.fullName) ?? "";
  const isRunning = useSessionStore((s) => s.isRunning);

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* ── Sidebar ── */}
      <aside className="w-52 shrink-0 bg-white flex flex-col border-r border-slate-200">
        <div className="px-4 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center shrink-0">
              <Briefcase className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="text-slate-900 font-bold text-sm leading-none truncate">JobAI</p>
              <p className="text-slate-400 text-[11px] mt-0.5 leading-none">Local job assistant</p>
            </div>
          </div>
        </div>

        {isRunning && (
          <div className="mx-3 mt-3 flex items-center gap-2 bg-emerald-50 border border-emerald-200
                          rounded-lg px-2.5 py-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span className="text-emerald-700 text-[11px] font-medium">Session running</span>
          </div>
        )}

        <nav className="flex-1 px-2.5 py-3 space-y-0.5">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-100"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-800 border border-transparent"
                }`
              }>
              <Icon className="w-4 h-4 shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-100 p-2.5 space-y-2">
          <ThemeToggle />
          <div className="flex items-center gap-2.5 px-2 py-1.5">
            <Avatar name={fullName} email={email} />
            <div className="flex-1 min-w-0">
              <p className="text-slate-700 text-xs font-medium truncate">{fullName || "Local User"}</p>
              <p className="text-slate-400 text-[11px] truncate">{email || "Runs entirely on this machine"}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
