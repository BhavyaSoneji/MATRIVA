const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "matriva_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(
      "Could not reach the MATRIVA backend. Please check your connection or try again later.",
      0
    );
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
      else if (Array.isArray(data?.detail)) {
        detail = data.detail.map((d: { msg?: string }) => d.msg).join(", ");
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { API_URL };

// ── /chat/stream ──────────────────────────────────────────────────────────
// Server-Sent Events wire format (see backend app/services/chat.py
// `stream_chat` docstring, the authoritative contract):
//   event: delta  data: {"text": string}
//   event: final  data: {"answer", "safety_status", "citations", "corrected"}
//   event: done   data: {"conversation_id", "message_id", "sources", "evidence", "recommendations"}
//   event: error  data: {"answer": string}
// `EventSource` can't send a POST body or an Authorization header, so this
// parses the SSE framing by hand over a streamed `fetch` body instead.

import type { Citation, SourceResponse, RecommendationResponse } from "./types";

export interface ChatStreamFinal {
  answer: string;
  safety_status: string;
  citations: Citation[];
  corrected: boolean;
}

export interface ChatStreamDone {
  conversation_id: string;
  message_id: string;
  sources: SourceResponse[];
  evidence: Record<string, unknown>;
  recommendations: RecommendationResponse[];
}

export interface ChatStreamHandlers {
  onDelta?: (text: string) => void;
  onFinal?: (data: ChatStreamFinal) => void;
  onDone?: (data: ChatStreamDone) => void;
  onError?: (message: string) => void;
}

export async function streamChat(
  payload: { message: string; conversation_id?: string },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    handlers.onError?.("Could not reach the MATRIVA backend. Please check your connection or try again later.");
    return;
  }

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
      else if (typeof data?.answer === "string") detail = data.answer;
    } catch {
      // ignore JSON parse errors
    }
    handlers.onError?.(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        const eventLine = frame.split("\n").find((l) => l.startsWith("event:"));
        const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
        if (eventLine && dataLine) {
          const type = eventLine.slice(6).trim();
          try {
            const data = JSON.parse(dataLine.slice(5).trim());
            if (type === "delta") handlers.onDelta?.(data.text ?? "");
            else if (type === "final") handlers.onFinal?.(data as ChatStreamFinal);
            else if (type === "done") handlers.onDone?.(data as ChatStreamDone);
            else if (type === "error") handlers.onError?.(data.answer ?? "Something went wrong.");
          } catch {
            // malformed frame -- skip rather than crash the stream
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    handlers.onError?.("The connection was interrupted. Please try again.");
  }
}
