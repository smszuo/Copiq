import { useState, type FormEvent } from "react";
import { checkConnection, ApiError } from "../lib/api";
import { saveSettings, type ConnectionSettings } from "../lib/settings";

export function Settings({ onSaved }: { onSaved: (s: ConnectionSettings) => void }) {
  const [server, setServer] = useState("http://127.0.0.1:5080");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setChecking(true);
    const trimmed = { server: server.replace(/\/$/, ""), apiKey: apiKey.trim() };
    try {
      await checkConnection(trimmed);
      saveSettings(trimmed);
      onSaved(trimmed);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("That API key was rejected by the server.");
      } else {
        setError(`Could not reach ${trimmed.server}. Is the server running?`);
      }
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm px-4">
      <h1 className="mb-1 text-xl font-semibold text-neutral-900 dark:text-neutral-100">Copiq</h1>
      <p className="mb-6 text-sm text-neutral-500 dark:text-neutral-400">Connect to your Copiq server.</p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
            Server URL
          </label>
          <input
            className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:focus:border-neutral-500"
            value={server}
            onChange={(e) => setServer(e.target.value)}
            placeholder="http://127.0.0.1:5080"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-neutral-700 dark:text-neutral-300">API key</label>
          <input
            className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-mono text-neutral-900 outline-none focus:border-neutral-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:focus:border-neutral-500"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="cw_..."
            type="password"
          />
          <p className="mt-1 text-xs text-neutral-400 dark:text-neutral-500">
            Create one with: <code>uv run python scripts/create_api_key.py --name web</code>
          </p>
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={checking || !apiKey || !server}
          className="w-full rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {checking ? "Connecting..." : "Connect"}
        </button>
      </form>
    </div>
  );
}
