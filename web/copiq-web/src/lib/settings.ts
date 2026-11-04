// Connection settings -- server URL + API key. architecture.md section 27:
// the browser presents a real Bearer token like any other client (see
// auth.py) rather than being trusted as same-origin, so it needs somewhere
// to hold that token. localStorage is per-origin and never leaves the
// browser; there is no server-side session.

export interface ConnectionSettings {
  server: string;
  apiKey: string;
}

const STORAGE_KEY = "copiq.connection";

export function loadSettings(): ConnectionSettings | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ConnectionSettings;
    if (!parsed.server || !parsed.apiKey) return null;
    return parsed;
  } catch {
    // Private browsing / blocked storage -- treat as unconfigured rather
    // than crash; the Settings screen will ask again.
    return null;
  }
}

export function saveSettings(settings: ConnectionSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function clearSettings(): void {
  localStorage.removeItem(STORAGE_KEY);
}
