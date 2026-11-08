// Phase 19 account + sharing client.
//
// Everything here is deliberately small and explicit: the account lifecycle endpoints return the
// same 202 for known and unknown addresses, and in a development server they also return the
// token so the flow can be exercised without a mail server. The UI surfaces that token only when
// the backend actually sends one, which production never does.
import { authorizationHeader } from "./auth";

const base = import.meta.env.VITE_API_BASE_URL || "/api";

async function request<T>(path: string, method: string, body?: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method,
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
        : payload?.message || `Request failed (${response.status})`,
    );
  return payload as T;
}

export type DeliveryMode = "smtp" | "outbox" | "unconfigured";

export interface ActivityEvent {
  kind: string;
  detail: string;
  createdAt: string;
}

export interface Readiness {
  status: string;
  database: string;
  databaseDialect: string;
  storage: { durable: boolean; reason: string; remedy: string };
  emailDelivery: DeliveryMode;
  shareLinks: boolean;
  rateLimitIdentity: "socket" | "forwarded";
  scientificValidation: string;
}

export const activityLabels: Record<string, string> = {
  "account-created": "Account created",
  login: "Signed in",
  "login-failed": "Failed sign-in attempt",
  logout: "Signed out",
  "email-verified": "Email address verified",
  "verification-requested": "Verification email requested",
  "password-changed": "Password changed",
  "password-reset-requested": "Password reset requested",
  "share-link-created": "Share link created",
  "share-link-revoked": "Share links revoked",
};

export const requestVerification = (email: string) =>
  request<{ status: string; delivery: DeliveryMode; debugToken?: string }>(
    "/auth/verify/request", "POST", { email });

export const confirmVerification = (token: string) =>
  request<{ status: string }>("/auth/verify/confirm", "POST", { token });

export const requestPasswordReset = (email: string) =>
  request<{ status: string; delivery: DeliveryMode; debugToken?: string }>(
    "/auth/password/forgot", "POST", { email });

export const resetPassword = (token: string, password: string) =>
  request<{ status: string; note: string }>("/auth/password/reset", "POST", { token, password });

export const fetchActivity = () =>
  request<{ events: ActivityEvent[] }>("/auth/activity", "GET");

export const fetchReadiness = () => request<Readiness>("/ready", "GET");

export interface ShareLink {
  token: string;
  url: string;
  expiresInDays: number;
  scope: string;
  disclaimer: string;
}

export const createShareLink = (scenarioId: string) =>
  request<ShareLink>(`/scenarios/${scenarioId}/share`, "POST");

export const revokeShareLinks = (scenarioId: string) =>
  request<{ revoked: number }>(`/scenarios/${scenarioId}/share`, "DELETE");

export interface SharedScenarioPayload {
  name: string;
  configuration: Record<string, string | number>;
  createdAt: string;
  modelVersion: string;
  expiresAt: string;
  result: Record<string, never>;
  scope: string;
  disclaimer: string;
  limitations: string[];
}

export const fetchSharedScenario = (token: string) =>
  request<SharedScenarioPayload>(`/shared/${encodeURIComponent(token)}`, "GET");

/** Absolute URL a person can paste into a message. */
export function shareUrl(token: string) {
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}/#shared/${token}`;
}
