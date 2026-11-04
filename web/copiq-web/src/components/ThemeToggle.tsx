import type { Theme } from "../lib/theme";

const OPTIONS: { value: Theme; label: string; title: string }[] = [
  { value: "light", label: "☀", title: "Light" },
  { value: "warm", label: "☕", title: "Warm (easier for long reading)" },
  { value: "dark", label: "☾", title: "Dark" },
  { value: "system", label: "◐", title: "Follow system" },
];

export function ThemeToggle({ theme, onChange }: { theme: Theme; onChange: (t: Theme) => void }) {
  return (
    <div className="flex rounded-md border border-neutral-300 dark:border-neutral-700">
      {OPTIONS.map((opt, i) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          title={opt.title}
          className={
            "px-2 py-1 text-xs " +
            (i > 0 ? "border-l border-neutral-300 dark:border-neutral-700 " : "") +
            (theme === opt.value
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "text-neutral-500 hover:bg-neutral-50 dark:text-neutral-400 dark:hover:bg-neutral-800")
          }
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
