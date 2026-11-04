// Wire contracts, mirrored by hand from copiq_shared/types.py and
// copiq_server/api/schemas.py -- there is no cross-language sync test
// for this pair (unlike the Python-side TypedDict/Pydantic split, see
// architecture.md section 9.1), so keep this file's shapes in step with
// the Python ones manually when either side changes.

export interface ClipboardItemOut {
  id: number;
  content: string;
  contentType: string;
  source: string;
  clientId: string;
  hasPossibleSecret: boolean;
  createdAt: string;
}

export interface ListResponse {
  items: ClipboardItemOut[];
  nextCursor: number | null;
  hasMore: boolean;
}

export type ActionName =
  | "translate"
  | "explain"
  | "explain-simple"
  | "simplify"
  | "summarize"
  | "breakdown"
  | "breakdown-target"
  | "skeleton"
  | "vocabulary"
  | "diagram";

export type DiagramType = "flowchart" | "sequence" | "class" | "er";

export interface ActionResponse {
  clipboardItemId: number;
  action: string;
  parameters: Record<string, string>;
  status: "pending" | "completed" | "failed";
  result: string | null;
  errorMessage: string | null;
  cached: boolean;
}
