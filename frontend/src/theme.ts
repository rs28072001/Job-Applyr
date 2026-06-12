// Light / dark / system theme with local persistence.

export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "sja-theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");

export function getThemeMode(): ThemeMode {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" || v === "system" ? v : "system";
}

function effectiveDark(mode: ThemeMode): boolean {
  return mode === "dark" || (mode === "system" && media.matches);
}

export function applyTheme(mode: ThemeMode): void {
  document.documentElement.classList.toggle("dark", effectiveDark(mode));
}

export function setThemeMode(mode: ThemeMode): void {
  localStorage.setItem(STORAGE_KEY, mode);
  applyTheme(mode);
}

export function initTheme(): void {
  applyTheme(getThemeMode());
  media.addEventListener("change", () => {
    if (getThemeMode() === "system") applyTheme("system");
  });
}
