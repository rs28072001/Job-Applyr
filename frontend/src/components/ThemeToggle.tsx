import { useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { getThemeMode, setThemeMode, type ThemeMode } from "../theme";

const OPTIONS: { mode: ThemeMode; icon: React.ElementType; label: string }[] = [
  { mode: "light", icon: Sun, label: "Light" },
  { mode: "dark", icon: Moon, label: "Dark" },
  { mode: "system", icon: Monitor, label: "System" },
];

export default function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(getThemeMode());

  function choose(m: ThemeMode) {
    setThemeMode(m);
    setMode(m);
  }

  return (
    <div className="flex items-center gap-0.5 bg-slate-100 rounded-lg p-0.5"
         role="radiogroup" aria-label="Theme">
      {OPTIONS.map(({ mode: m, icon: Icon, label }) => (
        <button key={m} type="button" title={label} aria-label={label}
          role="radio" aria-checked={mode === m}
          onClick={() => choose(m)}
          className={`flex-1 flex items-center justify-center py-1 rounded-md transition-colors ${
            mode === m
              ? "bg-white text-indigo-600 border border-slate-200"
              : "text-slate-400 hover:text-slate-600 border border-transparent"
          }`}>
          <Icon className="w-3.5 h-3.5" />
        </button>
      ))}
    </div>
  );
}
