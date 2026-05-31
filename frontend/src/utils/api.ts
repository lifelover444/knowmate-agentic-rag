const apiBase = "/api/v1";

function stringifyUnknown(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "请求失败，响应内容无法解析。";
  }
}

function formatLocation(loc: unknown): string {
  if (!Array.isArray(loc)) return "";
  return loc.filter((part) => part !== "body").join(".");
}

function formatValidationError(item: unknown): string {
  if (!item || typeof item !== "object") return stringifyUnknown(item);
  const record = item as Record<string, unknown>;
  const location = formatLocation(record.loc);
  const message = stringifyUnknown(record.msg ?? record.message ?? record);
  return location ? `${location}: ${message}` : message;
}

export function formatApiError(payload: unknown, fallback = "请求失败"): string {
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;

  if (typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const detail = record.detail ?? record.message ?? record.error;
    if (Array.isArray(detail)) {
      return detail.map(formatValidationError).filter(Boolean).join("；") || fallback;
    }
    if (detail && typeof detail === "object") return formatValidationError(detail);
    if (typeof detail === "string") return detail;
    const serialized = stringifyUnknown(payload);
    return serialized && serialized !== "{}" ? serialized : fallback;
  }

  return stringifyUnknown(payload) || fallback;
}

export function parseResponsePayload(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, options);
  const text = await response.text();
  const payload = parseResponsePayload(text);

  if (!response.ok) {
    throw new Error(formatApiError(payload, text || `HTTP ${response.status}`));
  }

  return payload as T;
}

function apiUrl(path: string): string {
  return `${apiBase}${path}`;
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(apiUrl(path));
}

export function getRootJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function postJson<T, P = unknown>(path: string, payload?: P): Promise<T> {
  return request<T>(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
}

export function putJson<T, P = unknown>(path: string, payload?: P): Promise<T> {
  return request<T>(apiUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
}

export function patchJson<T, P = unknown>(path: string, payload?: P): Promise<T> {
  return request<T>(apiUrl(path), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
}

export function deleteRequest<T = unknown>(path: string): Promise<T> {
  return request<T>(apiUrl(path), { method: "DELETE" });
}

export function postForm<T>(path: string, form: FormData): Promise<T> {
  return request<T>(apiUrl(path), {
    method: "POST",
    body: form,
  });
}

export async function downloadRequest(path: string): Promise<Blob> {
  const response = await fetch(apiUrl(path));
  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(parseResponsePayload(text), text || `HTTP ${response.status}`));
  }
  return response.blob();
}

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

export async function postSse<P = unknown>(
  path: string,
  payload: P,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(parseResponsePayload(text), text || `HTTP ${response.status}`));
  }
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const parsed = parseSseBlock(block);
      if (parsed) onEvent(parsed);
    }
  }
  const tail = parseSseBlock(buffer.trim());
  if (tail) onEvent(tail);
}

function parseSseBlock(block: string): SseEvent | null {
  if (!block) return null;
  let event = "message";
  let data = "{}";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data = line.slice(5).trim();
  }
  try {
    return { event, data: JSON.parse(data) as Record<string, unknown> };
  } catch {
    return { event, data: { error: data } };
  }
}
