import { useEffect, useState } from "react";
import { applyTheme, effectiveIsDark, loadTheme, saveTheme, type Theme } from "./theme";

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => loadTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    // Only relevant in "system" mode -- the OS-level preference can change
    // (e.g. sunset-triggered switch) without any click in this app.
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  function setTheme(next: Theme) {
    saveTheme(next);
    setThemeState(next);
  }

  return { theme, setTheme, isDark: effectiveIsDark(theme) };
}
