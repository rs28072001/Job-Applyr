import { NavLink, Outlet } from "react-router-dom";
import { useSessionStore } from "../../store/sessionStore";

const NAV = [
  { to: "/", label: "⚙️  Setup", end: true },
  { to: "/dashboard", label: "🚀  Dashboard" },
  { to: "/history", label: "📋  History" },
];

export default function AppShell() {
  const isRunning = useSessionStore((s) => s.isRunning);

  return (
    <div className="flex min-h-screen bg-gray-50 text-gray-900">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 text-white flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-gray-700">
          <p className="text-xs uppercase tracking-widest text-gray-400 mb-1">Smart Job</p>
          <h1 className="text-lg font-bold leading-tight">Job Assistant</h1>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        {isRunning && (
          <div className="px-4 py-3 border-t border-gray-700">
            <span className="inline-flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              Session running
            </span>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
