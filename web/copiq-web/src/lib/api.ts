import type { ActionName, ActionResponse, DiagramType, ListResponse } from "./types";
import type { ConnectionSettings } from "./settings";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(`HTTP ${status}: ${JSON.stringify(detail)}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  settings: ConnectionSettings,
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${settings.server}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${settings.apiKey}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? data.detail : data;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export function listClipboard(
  settings: ConnectionSettings,
  opts: { limit?: number; before?: number; search?: string } = {},
): Promise<ListResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.before) params.set("before", String(opts.before));
  if (opts.search) params.set("search", opts.search);
  const qs = params.toString();
  return request<ListResponse>(settings, "GET", `/api/clipboard${qs ? `?${qs}` : ""}`);
}

export function deleteClipboardItem(settings: ConnectionSettings, id: number): Promise<void> {
  return request<void>(settings, "DELETE", `/api/clipboard/${id}`);
}

export function runAction(
  settings: ConnectionSettings,
  id: number,
  action: ActionName,
  opts: { targetLanguage?: string; diagramType?: DiagramType; acknowledgeSecret?: boolean } = {},
): Promise<ActionResponse> {
  const parameters: Record<string, string> = {};
  if (opts.targetLanguage) parameters.targetLanguage = opts.targetLanguage;
  if (opts.diagramType) parameters.diagramType = opts.diagramType;
  return request<ActionResponse>(settings, "POST", `/api/clipboard/${id}/actions`, {
    action,
    parameters: Object.keys(parameters).length ? parameters : undefined,
    acknowledgeSecret: opts.acknowledgeSecret ?? false,
  });
}

export function checkConnection(settings: ConnectionSettings): Promise<void> {
  return request<void>(settings, "GET", "/api/clipboard?limit=1");
}

// Separate from request(): the body is an MP3, not JSON. An <audio src> can't
// send the Authorization header, so the caller plays the Blob via an object URL.
export async function fetchItemAudio(
  settings: ConnectionSettings,
  id: number,
  acknowledgeSecret: boolean,
): Promise<Blob> {
  const res = await fetch(`${settings.server}/api/clipboard/${id}/audio?acknowledgeSecret=${acknowledgeSecret}`, {
    headers: { Authorization: `Bearer ${settings.apiKey}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => undefined);
    throw new ApiError(res.status, data && typeof data === "object" && "detail" in data ? data.detail : data);
  }
  return res.blob();
}
