import type {
  ApiErrorPayload,
  PlaceSuggestion,
  RoutePlanRequest,
  RoutePlanResponse,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function planRoutes(
  input: RoutePlanRequest,
): Promise<RoutePlanResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/route-plans/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    throw new ApiRequestError(
      0,
      "Could not reach the StormHaul API. Is the backend running?",
    );
  }

  const payload = (await response.json().catch(() => null)) as
    | RoutePlanResponse
    | ApiErrorPayload
    | null;

  if (!response.ok) {
    const errorPayload = payload as ApiErrorPayload | null;
    throw new ApiRequestError(
      response.status,
      errorPayload?.error?.message ?? `Request failed (HTTP ${response.status}).`,
      errorPayload?.error?.details,
    );
  }

  return payload as RoutePlanResponse;
}

export async function searchPlaces(
  query: string,
  signal?: AbortSignal,
): Promise<PlaceSuggestion[]> {
  const trimmed = query.trim();
  if (trimmed.length < 2) {
    return [];
  }
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE}/api/locations/?q=${encodeURIComponent(trimmed)}`,
      { signal },
    );
  } catch {
    return [];
  }
  if (!response.ok) {
    return [];
  }
  const payload = (await response.json().catch(() => null)) as
    | { results?: PlaceSuggestion[] }
    | null;
  return payload?.results ?? [];
}
