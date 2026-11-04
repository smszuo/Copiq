import { useState } from "react";
import { History } from "./components/History";
import { Settings } from "./components/Settings";
import { ThemeToggle } from "./components/ThemeToggle";
import { clearSettings, loadSettings, type ConnectionSettings } from "./lib/settings";
import { useTheme } from "./lib/useTheme";

export default function App() {
  const [settings, setSettings] = useState<ConnectionSettings | null>(() => loadSettings());
  const { theme, setTheme, isDark } = useTheme();

  if (!settings) {
    return (
      <div className="min-h-screen bg-white dark:bg-neutral-950">
        <div className="mx-auto flex max-w-sm justify-end px-4 pt-4">
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
        <Settings onSaved={setSettings} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white dark:bg-neutral-950">
      <History settings={settings} isDark={isDark} themeControl={<ThemeToggle theme={theme} onChange={setTheme} />} />
      <div className="mx-auto max-w-2xl px-4 pb-8">
        <button
          onClick={() => {
            clearSettings();
            setSettings(null);
          }}
          className="text-xs text-neutral-400 hover:text-neutral-600 dark:text-neutral-500 dark:hover:text-neutral-300"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
}
