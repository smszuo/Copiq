import { useEffect, useRef, useState } from "react";
import { ApiError, deleteClipboardItem, fetchItemAudio, runAction } from "../lib/api";
import { renderMermaid } from "../lib/mermaid";
import type { ActionName, ClipboardItemOut, DiagramType } from "../lib/types";
import type { ConnectionSettings } from "../lib/settings";

// Text actions render as plain text; diagram gets its own button, its own
// optional type selector, and its own SVG-rendering result slot below,
// since its result isn't text to display but Mermaid source to render.
// The (XX) suffix is the language of the result.
// shortcut: (CN) assumes the server's default_target_language is zh-CN; fetch it from the server if that ever changes.
const TEXT_ACTIONS: { action: ActionName; label: string; title: string }[] = [
  { action: "translate", label: "Translate (CN)", title: "Translate into Chinese" },
  { action: "explain", label: "Explain (CN)", title: "Explain in Chinese" },
  { action: "explain-simple", label: "Explain (EN)", title: "Explain in simple English" },
  { action: "simplify", label: "Simplify (EN)", title: "Rewrite in simple English" },
  { action: "summarize", label: "Summary (EN)", title: "One-sentence summary in simple English" },
  { action: "breakdown", label: "Breakdown (EN)", title: "Sentence breakdown: split each sentence into its parts and explain them in English" },
  { action: "breakdown-target", label: "Breakdown (CN)", title: "Sentence breakdown: split each sentence into its parts and explain them in Chinese" },
  { action: "skeleton", label: "Skeleton (EN)", title: "Sentence skeleton: the core subject, verb, and object of each sentence" },
  { action: "vocabulary", label: "Key Vocabulary (EN+CN)", title: "Key words and phrases, each with a simple English meaning and a Chinese translation" },
];

const DIAGRAM_TYPES: { value: DiagramType | ""; label: string }[] = [
  { value: "", label: "Auto" },
  { value: "flowchart", label: "Flowchart" },
  { value: "sequence", label: "Sequence" },
  { value: "class", label: "Class" },
  { value: "er", label: "ER" },
];

export function ItemCard({
  item,
  settings,
  isDark,
  onDeleted,
}: {
  item: ClipboardItemOut;
  settings: ConnectionSettings;
  isDark: boolean;
  onDeleted: (id: number) => void;
}) {
  const [results, setResults] = useState<Partial<Record<ActionName, string>>>({});
  const [errors, setErrors] = useState<Partial<Record<ActionName, string>>>({});
  const [pending, setPending] = useState<ActionName | null>(null);
  const [ack, setAck] = useState(false);
  const [diagramType, setDiagramType] = useState<DiagramType | "">("");
  const [audioState, setAudioState] = useState<"idle" | "loading" | "playing">("idle");
  const [audioError, setAudioError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  // Stop playback and free the MP3 when the card goes away.
  useEffect(
    () => () => {
      audioRef.current?.pause();
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    },
    [],
  );

  async function handleAudio() {
    if (audioState === "playing") {
      audioRef.current?.pause();
      setAudioState("idle");
      return;
    }
    setAudioError(null);
    try {
      // Fetch once per card; replays reuse the same MP3.
      if (!audioUrlRef.current) {
        setAudioState("loading");
        audioUrlRef.current = URL.createObjectURL(await fetchItemAudio(settings, item.id, ack));
        audioRef.current = new Audio(audioUrlRef.current);
        audioRef.current.onended = () => setAudioState("idle");
      }
      audioRef.current!.currentTime = 0;
      await audioRef.current!.play();
      setAudioState("playing");
    } catch (err) {
      setAudioState("idle");
      if (err instanceof ApiError && err.status === 409) {
        setAudioError("Flagged as a possible secret. Check the box below to play anyway.");
      } else if (err instanceof ApiError) {
        setAudioError(String(err.detail));
      } else {
        setAudioError("Could not play audio.");
      }
    }
  }

  async function handleAction(action: ActionName, opts: { diagramType?: DiagramType } = {}) {
    setPending(action);
    setErrors((e) => ({ ...e, [action]: undefined }));
    try {
      const res = await runAction(settings, item.id, action, {
        acknowledgeSecret: ack,
        ...opts,
      });
      setResults((r) => ({ ...r, [action]: res.result ?? "" }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErrors((e) => ({ ...e, [action]: "Flagged as a possible secret. Check the box below to run anyway." }));
      } else if (err instanceof ApiError) {
        setErrors((e) => ({ ...e, [action]: String(err.detail) }));
      } else {
        setErrors((e) => ({ ...e, [action]: "Request failed." }));
      }
    } finally {
      setPending(null);
    }
  }

  async function handleDelete() {
    await deleteClipboardItem(settings, item.id);
    onDeleted(item.id);
  }

  return (
    <div className="border-b border-neutral-200 py-4 dark:border-neutral-800">
      <div className="mb-1 flex items-center justify-between">
        <time className="text-xs text-neutral-400 dark:text-neutral-500">
          {new Date(item.createdAt).toLocaleString()}
        </time>
        {item.hasPossibleSecret && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-400">
            ⚠ possible secret
          </span>
        )}
      </div>
      <pre className="mb-2 whitespace-pre-wrap break-words font-sans text-sm text-neutral-800 dark:text-neutral-200">
        {item.content}
      </pre>

      {item.hasPossibleSecret && (
        <label className="mb-2 flex items-center gap-1.5 text-xs text-neutral-500 dark:text-neutral-400">
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          Run AI actions and audio on this anyway
        </label>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={handleAudio}
          disabled={audioState === "loading"}
          title={audioState === "playing" ? "Stop" : "Read the text aloud (US English, male voice)"}
          className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          {audioState === "loading" ? "..." : audioState === "playing" ? "■ Stop" : "▶ Listen (EN)"}
        </button>
        {TEXT_ACTIONS.map(({ action, label, title }) => (
          <button
            key={action}
            onClick={() => handleAction(action)}
            title={title}
            disabled={pending === action}
            className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            {pending === action ? "..." : label}
          </button>
        ))}

        <button
          onClick={() => handleAction("diagram", diagramType ? { diagramType } : {})}
          disabled={pending === "diagram"}
          className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          {pending === "diagram" ? "..." : "Diagram"}
        </button>
        <select
          value={diagramType}
          onChange={(e) => setDiagramType(e.target.value as DiagramType | "")}
          className="rounded-md border border-neutral-300 bg-white px-1.5 py-1 text-xs text-neutral-600 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400"
          title="Mermaid diagram type"
        >
          {DIAGRAM_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>

        <button
          onClick={handleDelete}
          className="ml-auto rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:border-neutral-700 dark:text-red-400 dark:hover:bg-red-950/40"
        >
          Delete
        </button>
      </div>

      {audioError && (
        <div className="mt-2 rounded-md bg-red-50 p-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
          {audioError}
        </div>
      )}

      {TEXT_ACTIONS.map(({ action }) =>
        results[action] || errors[action] ? (
          <div
            key={action}
            className={
              errors[action]
                ? "mt-2 rounded-md bg-red-50 p-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400"
                : "mt-2 whitespace-pre-wrap rounded-md bg-neutral-100 p-2 text-sm text-neutral-800 dark:bg-neutral-900 dark:text-neutral-200"
            }
          >
            {errors[action] ?? results[action]}
          </div>
        ) : null,
      )}

      {errors.diagram && (
        <div className="mt-2 rounded-md bg-red-50 p-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
          {errors.diagram}
        </div>
      )}
      {results.diagram && <DiagramResult source={results.diagram} isDark={isDark} />}
    </div>
  );
}

function DiagramResult({ source, isDark }: { source: string; isDark: boolean }) {
  const [state, setState] = useState<
    { status: "loading" } | { status: "ok"; svg: string } | { status: "error"; message: string }
  >({ status: "loading" });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    // isDark is a dependency deliberately: toggling the theme re-renders an
    // already-displayed diagram in the new palette immediately, rather than
    // only affecting the next diagram generated from here on.
    renderMermaid(source, isDark).then((result) => {
      if (cancelled) return;
      setState(result.ok ? { status: "ok", svg: result.svg } : { status: "error", message: result.error });
    });
    return () => {
      cancelled = true;
    };
  }, [source, isDark]);

  useEffect(() => {
    // Escape already exits full screen natively -- this just keeps the
    // button label in sync (including when the browser's own Escape
    // handling fires, not just our own exitFullscreen() calls).
    function onChange() {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    }
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await containerRef.current?.requestFullscreen();
      }
    } catch (err) {
      // Fullscreen can be refused (no user gesture, an embedding iframe
      // without allow="fullscreen", a browser without support) -- the
      // diagram stays visible inline either way, so fail quietly rather
      // than surface this as a card error.
      console.warn("Fullscreen request failed:", err);
    }
  }

  if (state.status === "loading") {
    return <div className="mt-2 text-xs text-neutral-400 dark:text-neutral-500">Rendering diagram...</div>;
  }

  if (state.status === "error") {
    // Models don't always produce syntactically valid Mermaid -- show the
    // raw source rather than just failing silently.
    return (
      <div className="mt-2">
        <div className="rounded-md bg-red-50 p-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
          Could not render as a diagram: {state.message}
        </div>
        <pre className="mt-1 whitespace-pre-wrap rounded-md bg-neutral-100 p-2 text-xs text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400">
          {source}
        </pre>
      </div>
    );
  }

  // Safe: securityLevel "strict" (lib/mermaid.ts) sanitizes the SVG mermaid
  // produces from this AI-derived (untrusted) source before we ever reach
  // this dangerouslySetInnerHTML -- see the comment there before changing
  // either side of this.
  return (
    <div
      ref={containerRef}
      className={
        isFullscreen
          ? // Mermaid's SVG ships `width="100%"`, no `height` attribute, and
            // an inline `style="max-width: <n>px"` sized to its small inline
            // card. `height: auto` never derives a real height here (no
            // intrinsic height to fall back to, unlike an <img>), and the
            // inline max-width -- being inline, not a stylesheet rule --
            // beats a plain CSS class regardless of specificity, so it has
            // to be overridden with `!important` too or it silently clamps
            // the width back down. Force both dimensions to fill this box
            // and remove the max- constraints entirely; the SVG's own
            // viewBox + preserveAspectRatio="xMidYMid meet" (mermaid's
            // default) does the actual letterboxing internally.
            "relative flex h-full w-full items-center justify-center bg-white p-8 [&_svg]:!h-full [&_svg]:!w-full [&_svg]:!max-w-none [&_svg]:!max-h-none dark:bg-neutral-900"
          : "relative mt-2 overflow-x-auto rounded-md border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900"
      }
    >
      <button
        onClick={toggleFullscreen}
        title={isFullscreen ? "Exit full screen" : "Full screen"}
        className="absolute right-2 top-2 rounded-md border border-neutral-300 bg-white/90 px-2 py-1 text-xs text-neutral-600 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900/90 dark:text-neutral-400 dark:hover:bg-neutral-800"
      >
        {isFullscreen ? "✕ Exit" : "⛶"}
      </button>
      <div
        className={isFullscreen ? "h-full w-full" : undefined}
        dangerouslySetInnerHTML={{ __html: state.svg }}
      />
    </div>
  );
}
