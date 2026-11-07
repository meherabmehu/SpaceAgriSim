const base = import.meta.env.VITE_API_BASE_URL || "/api";
const KEY = "spaceagrisim.auth";

export type Session = { accessToken: string; expiresAt: string; user: { id: string; email: string } };

export function readSession(): Session | null {
  try {
    const value = localStorage.getItem(KEY);
    if (!value) return null;
    const session = JSON.parse(value) as Session;
    if (!session.accessToken || Date.parse(session.expiresAt) <= Date.now()) {
      localStorage.removeItem(KEY);
      return null;
    }
    return session;
  } catch { return null; }
}

export function authorizationHeader(): Record<string, string> {
  const session = readSession();
  return session ? { Authorization: `Bearer ${session.accessToken}` } : {};
}

export function clearSession() { localStorage.removeItem(KEY); }

export async function authenticate(mode: "login" | "register", email: string, password: string): Promise<Session> {
  const response = await fetch(`${base}/auth/${mode}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.message || data?.detail || "Authentication failed");
  const session: Session = { accessToken: data.accessToken, expiresAt: data.expiresAt, user: data.user };
  localStorage.setItem(KEY, JSON.stringify(session));
  return session;
}

export async function logout() {
  const headers = authorizationHeader();
  try { await fetch(`${base}/auth/logout`, { method: "POST", headers }); } finally { clearSession(); }
}
