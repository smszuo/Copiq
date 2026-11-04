import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { listClipboard } from "../lib/api";
import type { ClipboardItemOut } from "../lib/types";
import type { ConnectionSettings } from "../lib/settings";
import { ItemCard } from "./ItemCard";

const PAGE_SIZE = 50;

export function History({
  settings,
  isDark,
  themeControl,
}: {
  settings: ConnectionSettings;
  isDark: boolean;
  themeControl: ReactNode;
}) {
  const [items, setItems] = useState<ClipboardItemOut[]>([]);
  const [search, setSearch] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  // architecture.md section 26 -- no polling interval; refresh on window
  // focus plus a manual button. The actual workflow is "copy in the
  // terminal, switch to the browser" -- the switch is the signal.
  const reload = useCallback(
    async (searchValue: string) => {
      setLoading(true);
      try {
        const res = await listClipboard(settings, { limit: PAGE_SIZE, search: searchValue || undefined });
        setItems(res.items);
        setHasMore(res.hasMore);
        setNextCursor(res.nextCursor);
      } finally {
        setLoading(false);
      }
    },
    [settings],
  );

  const searchRef = useRef(search);
  searchRef.current = search;

  useEffect(() => {
    reload(searchRef.current);
    const onFocus = () => reload(searchRef.current);
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [reload]);

  useEffect(() => {
    const id = setTimeout(() => reload(search), 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function loadMore() {
    if (!nextCursor) return;
    setLoading(true);
    try {
      const res = await listClipboard(settings, { limit: PAGE_SIZE, before: nextCursor, search: search || undefined });
      setItems((prev) => [...prev, ...res.items]);
      setHasMore(res.hasMore);
      setNextCursor(res.nextCursor);
    } finally {
      setLoading(false);
    }
  }

  function handleDeleted(id: number) {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Copiq</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => reload(search)}
            className="text-sm text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          {themeControl}
        </div>
      </div>
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search clipboard history..."
        className="mb-4 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:focus:border-neutral-500"
      />

      {items.length === 0 && !loading && (
        <p className="py-8 text-center text-sm text-neutral-400 dark:text-neutral-500">No clipboard items yet.</p>
      )}

      <div>
        {items.map((item) => (
          <ItemCard key={item.id} item={item} settings={settings} isDark={isDark} onDeleted={handleDeleted} />
        ))}
      </div>

      {hasMore && (
        <button
          onClick={loadMore}
          disabled={loading}
          className="mt-4 w-full rounded-md border border-neutral-300 py-2 text-sm text-neutral-600 hover:bg-neutral-50 disabled:opacity-40 dark:border-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-800"
        >
          {loading ? "Loading..." : "Load more"}
        </button>
      )}
    </div>
  );
}
