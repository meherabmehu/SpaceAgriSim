import { authorizationHeader } from "./auth";

/**
 * Downloads, kept out of the entry chunk.
 *
 * This module is imported dynamically by the two places that offer an export - the mission
 * workspace header and the measured-band panel. The bundle guard holds the initial request to
 * 240 kB, and a file-saving helper that is only reachable after a click does not belong in the
 * bundle every visitor pays for before the first render. Nothing here runs on load.
 */

const base = import.meta.env.VITE_API_BASE_URL || "/api";

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

/**
 * The filename the server chose, from `Content-Disposition`.
 *
 * A download that names itself on the client is a download whose name is a guess: the server knows
 * which configuration, factor and date the file contains, and the browser only knows the format.
 * The server's name is used when it sends one; the caller's fallback is used only when a proxy has
 * stripped the header.
 */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  // `filename*=UTF-8''a%20b.csv` is the extended form; the plain form is quoted.
  const extended = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      /* a malformed escape is not worth failing a download over */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : fallback;
}

/**
 * POST a request, then save the returned bytes under the name the server gave them.
 *
 * Returns the filename so the caller can state what was actually written rather than announcing a
 * download that may have been an error page. A non-2xx response is read for its message first:
 * `fetch` resolves on 422 just as happily as on 200, and a blob of `{"error": ...}` saved as
 * `report.pdf` is a corrupt file presented as success.
 */
export async function postForFile(
  path: string,
  body: unknown,
  fallbackName: string,
): Promise<{ filename: string; bytes: number }> {
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { ...authorizationHeader(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: unknown; message?: unknown }
      | null;
    const detail = typeof payload?.detail === "string" ? payload.detail : "";
    const message = typeof payload?.message === "string" ? payload.message : "";
    throw new Error(detail || message || `Export failed (${response.status})`);
  }
  const blob = await response.blob();
  if (blob.size === 0) throw new Error("The server returned an empty file");
  const filename = filenameFromDisposition(
    response.headers.get("Content-Disposition"),
    fallbackName,
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { filename, bytes: blob.size };
}

export async function downloadReport(format: "csv" | "pdf", params: MissionParameters) {
  return postForFile(`/reports/${format}`, params, `spaceagrisim-mission.${format}`);
}
