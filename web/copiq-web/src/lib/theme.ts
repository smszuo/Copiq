export type Theme = "light" | "warm" | "dark" | "system";

const STORAGE_KEY = "copiq.theme";

export function loadTheme(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "warm" || v === "dark" || v === "system") return v;
  } catch {
    // private browsing / blocked storage -- fall through to the default
  }
  return "system";
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // best-effort; a failed save just means "system" next reload
  }
}

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function effectiveIsDark(theme: Theme): boolean {
  return theme === "dark" || (theme === "system" && systemPrefersDark());
}

// Toggles the .dark class Tailwind's dark: variant is configured to key off
// (see index.css's @custom-variant) -- this is what actually switches the
// rendered colors, independent of whatever React state triggered it.
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", effectiveIsDark(theme));
  // "warm" is a light theme with the neutral palette swapped (see index.css).
  document.documentElement.classList.toggle("warm", theme === "warm");
}
