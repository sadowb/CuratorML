export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

const configuredApiBase = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL ?? "",
);
const defaultApiBases = [
  "http://127.0.0.1:8000/api/v1",
  "http://localhost:8000/api/v1",
  "/api/v1",
];
const apiBaseCandidates = Array.from(
  new Set(
    [configuredApiBase || null, ...defaultApiBases]
      .filter((value): value is string => Boolean(value))
      .map(trimTrailingSlash),
  ),
);

let activeApiBase = apiBaseCandidates[0] ?? "http://127.0.0.1:8000/api/v1";

function apiOriginFromBase(base: string): string {
  return base.replace(/\/api\/v1$/, "");
}

export function isLikelyHtmlContentType(contentType: string | null): boolean {
  return (contentType ?? "").toLowerCase().includes("text/html");
}

export function getApiBaseAttemptOrder(): string[] {
  return [
    activeApiBase,
    ...apiBaseCandidates.filter((base) => base !== activeApiBase),
  ];
}

export function setActiveApiBase(base: string): void {
  activeApiBase = base;
}

function getAttemptedBasesLabel(): string {
  return getApiBaseAttemptOrder().join(", ");
}

export function extractApiErrorMessage(
  responseText: string,
  fallback: string,
): string {
  if (!responseText) {
    return fallback;
  }

  try {
    const data = JSON.parse(responseText) as {
      detail?: string | Array<{ msg?: string; loc?: unknown[]; type?: string }>;
      message?: string;
    };
    if (data?.detail) {
      if (typeof data.detail === "string") {
        return data.detail;
      }
      if (Array.isArray(data.detail)) {
        return data.detail.map((e) => e.msg ?? JSON.stringify(e)).join("; ");
      }
    }
    if (data?.message) {
      return data.message;
    }
  } catch {
    // Fallback below handles non-JSON responses.
  }

  return responseText.slice(0, 220) || fallback;
}

async function fetchWithBaseFallback(
  path: string,
  init: RequestInit,
): Promise<{ response: Response; base: string }> {
  let lastError: unknown = null;

  for (const base of getApiBaseAttemptOrder()) {
    try {
      const response = await fetch(`${base}${path}`, init);
      const contentType = response.headers.get("content-type");

      if (isLikelyHtmlContentType(contentType)) {
        lastError = new Error(`Received HTML response from ${base}${path}`);
        continue;
      }

      setActiveApiBase(base);
      return { response, base };
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const isBodyMethod = ["POST", "PUT", "PATCH"].includes(method);
  const clientRequestId = crypto.randomUUID();
  const headers = new Headers(init?.headers ?? {});
  const body = init?.body;
  const isFormData =
    typeof FormData !== "undefined" && body instanceof FormData;

  if (isBodyMethod && body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const startedAt = performance.now();
  let response: Response;
  let resolvedBase = "";

  try {
    const result = await fetchWithBaseFallback(path, {
      ...init,
      method,
      headers,
    });
    response = result.response;
    resolvedBase = result.base;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network error";
    throw new ApiError(
      `Failed to reach API (attempted: ${getAttemptedBasesLabel()}). ${message}`,
      0,
    );
  }

  const durationMs = performance.now() - startedAt;
  const responseRequestId = response.headers.get("x-request-id") ?? "n/a";
  console.debug(
    `[api] ${method} ${path} -> ${response.status} (${durationMs.toFixed(1)}ms) base=${resolvedBase} client=${clientRequestId} server=${responseRequestId}`,
  );

  const responseText = response.status === 204 ? "" : await response.text();

  if (!response.ok) {
    throw new ApiError(
      extractApiErrorMessage(
        responseText,
        `Request failed with status ${response.status}`,
      ),
      response.status,
    );
  }

  if (response.status === 204) {
    return {} as T;
  }

  try {
    return JSON.parse(responseText) as T;
  } catch {
    const contentType = response.headers.get("content-type") ?? "unknown";
    throw new ApiError(
      `Invalid API response from ${resolvedBase}${path}: expected JSON but received ${contentType}.`,
      response.status,
    );
  }
}

export function toAbsoluteApiUrl(url: string | null | undefined): string {
  if (!url) {
    return "";
  }

  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }

  if (url.startsWith("/")) {
    return `${apiOriginFromBase(activeApiBase)}${url}`;
  }

  return `${apiOriginFromBase(activeApiBase)}/${url}`;
}
