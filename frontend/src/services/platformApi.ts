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
  const payload = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : payload?.message || `API request failed (${response.status})`,
    );
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

