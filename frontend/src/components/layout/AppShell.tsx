import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Briefcase, Settings, LayoutDashboard, History, LogOut, ChevronRight } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useSessionStore } from "../../store/sessionStore";

const NAV: Array<{
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
}> = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/setup", label: "Setup",     icon: Settings },
  { to: "/history",   label: "History",   icon: History   },
];

function Avatar({ name, email }: { name: string; email: string }) {
  const initials = name
    ? name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
    : email.slice(0, 2).toUpperCase();
  return (
    <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center
                    text-white text-xs font-bold shrink-0">
      {initials}
    </div>
  );
}

export default function AppShell() {
  const navigate    = useNavigate();
  const logout      = useAuthStore((s) => s.logout);
  const email       = useAuthStore((s) => s.email) ?? "";
  const fullName    = useAuthStore((s) => s.fullName) ?? "";
  const isRunning   = useSessionStore((s) => s.isRunning);

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* ── Sidebar ── */}
      <aside className="w-60 shrink-0 bg-slate-900 flex flex-col border-r border-slate-800">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center shrink-0">
              <Briefcase className="w-4 h-4 text-white" />
            </div>
            <div className="min-w-0">
              <p className="text-white font-bold text-sm leading-none truncate">JobAI</p>
              <p className="text-slate-500 text-xs mt-0.5 leading-none">Smart Job Assistant</p>
            </div>
          </div>
        </div>

        {/* Session status banner */}
        {isRunning && (
          <div className="mx-3 mt-3 flex items-center gap-2 bg-emerald-900/40 border border-emerald-700/50
                          rounded-lg px-3 py-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
            <span className="text-emerald-300 text-xs font-medium">Session running</span>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                 transition-all duration-150 ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="flex-1">{label}</span>
                  {isActive && <ChevronRight className="w-3 h-3 opacity-60" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="border-t border-slate-800 p-3">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-slate-800
                          cursor-default group">
            <Avatar name={fullName} email={email} />
            <div className="flex-1 min-w-0">
              <p className="text-white text-xs font-medium truncate">{fullName || "User"}</p>
              <p className="text-slate-500 text-xs truncate">{email}</p>
            </div>
            <button onClick={handleLogout} title="Sign out"
              className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400
                         p-1 rounded transition-all">
              <LogOut className="w-3.5 h-3.5" />
            </button>
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
