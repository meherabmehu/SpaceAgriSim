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

