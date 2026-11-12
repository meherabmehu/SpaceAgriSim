import { authorizationHeader } from "./auth";

export interface MissionParameters {
  crop: string;
  radiation: number;
  waterAvailability: number;
  lightHours: number;
  co2Level: number;
  growingArea: number;
  simulationDays: number;
  earthComparisonMode: "matched" | "baseline";
  lightIntensity: number;
  temperature: number;
  humidity: number;
  lightSpectrum: string;
  waterRecyclingEfficiency: number;
}
const base = import.meta.env.VITE_API_BASE_URL || "/api";

/**
 * Was this rejection a cancellation rather than a failure?
 *
 * `fetch` rejects with a `DOMException` named `AbortError` when its signal fires, and a body read
 * throws the same name when the stream is cancelled mid-read. Callers must be able to tell the two
 * apart from a real failure: a cancelled request is not an error to show the user, and a component
 * that reports one as an error has invented a fault that did not happen.
 */
export function isAbortError(error: unknown): boolean {
  return (error as { name?: string } | null | undefined)?.name === "AbortError";
}

export async function api<T = Record<string, unknown>>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  // A guard, not decoration: the resource hook used to pass a `null` path straight through and the
  // template below turned it into the request `GET /apinull` (404 in the console, signed out). Any
  // future caller that forgets to gate a resource now gets a named error instead of a phantom URL.
  if (typeof path !== "string" || !path.startsWith("/"))
    throw new Error(`Invalid API path: ${String(path)}`);
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? "GET" : "POST",
    signal,
    headers: {
      ...authorizationHeader(),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  // A body that is not JSON - an empty 204, a proxy's HTML error page - is not an error by itself:
  // the status line decides that, and `.catch` exists so a non-JSON failure body still surfaces as
  // a status message. A *cancelled* read is not that case. Swallowing it here turned `abort()` into
  // a resolved `null`, so a request the caller had deliberately cancelled came back as
  // "loaded successfully, no data" and overwrote whatever the caller was showing.
  const payload: { detail?: unknown; message?: unknown } | null = await response
    .json()
    .catch((error) => {
      if (isAbortError(error)) throw error;
      return null;
    });
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : "";
    const message = typeof payload?.message === "string" ? payload.message : "";
    throw new Error(detail || message || `API request failed (${response.status})`);
  }
  return payload as T;
}
export async function downloadReport(
  format: "json" | "csv" | "pdf",
  params: MissionParameters,
) {
  const response = await fetch(`${base}/reports/${format}`, {
    method: "POST",
    headers: { ...authorizationHeader(), "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!response.ok) throw new Error(`Report failed (${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `spaceagrisim-mission.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

