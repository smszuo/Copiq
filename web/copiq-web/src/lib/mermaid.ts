// Dynamically imported, not `import mermaid from "mermaid"` at module top
// level: mermaid's core runtime alone is ~900KB before gzip, and every
// diagram type (gantt, C4, cytoscape layouts, katex for math...) we don't
// use ships as its own chunk. A static import would put that weight in
// every page load, for every user, even the ones who never click
// "Diagram". Dynamic import defers fetching it until the first actual use.
type MermaidModule = typeof import("mermaid");
let mermaidPromise: Promise<MermaidModule> | null = null;

function loadMermaid(): Promise<MermaidModule> {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid");
  }
  return mermaidPromise;
}

// mermaid.initialize() is global config, not a per-render option -- switching
// the app's theme has to re-call it before the next render() picks up the
// new palette. Tracked so repeated renders in the same theme don't
// re-initialize for no reason.
let initializedTheme: "default" | "dark" | null = null;

function ensureTheme(mermaid: MermaidModule["default"], theme: "default" | "dark") {
  if (initializedTheme === theme) return;
  // architecture.md section 17.1 -- Mermaid *source* here is AI output
  // derived from untrusted clipboard content, same prompt-injection framing
  // as every other action's result. `securityLevel: "strict"` sanitizes
  // HTML/click-handlers embedded in node labels; the default-adjacent
  // "loose" level does not. Do not relax this without re-reading that
  // section -- this project already shipped one XSS bug in the Web UI (the
  // htmx-inheritance fix, see git history) from under-treating AI output as
  // untrusted when rendering it.
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme });
  initializedTheme = theme;
}

// The server already extracts the fenced ```mermaid block server-side
// (copiq_server/application/actions.py: postprocess_result), so `source`
// here should already be bare Mermaid syntax -- this is a second,
// client-side safety net in case that ever changes or a cached row
// predates it.
const FENCE_RE = /```(?:mermaid)?\s*\n([\s\S]*?)```/;

export function extractMermaidSource(raw: string): string {
  const match = FENCE_RE.exec(raw);
  return (match ? match[1] : raw).trim();
}

export type RenderResult = { ok: true; svg: string } | { ok: false; error: string };

let renderCounter = 0;

export async function renderMermaid(source: string, isDark: boolean): Promise<RenderResult> {
  const { default: mermaid } = await loadMermaid();
  ensureTheme(mermaid, isDark ? "dark" : "default");
  const id = `mermaid-${++renderCounter}`;
  try {
    const { svg } = await mermaid.render(id, extractMermaidSource(source));
    return { ok: true, svg };
  } catch (err) {
    // Models don't always produce syntactically valid Mermaid -- fall back
    // to showing the raw source rather than crashing the card.
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}
