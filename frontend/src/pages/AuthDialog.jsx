import { useState } from "react";
import { authenticate, clearSession } from "../services/auth.ts";
import { confirmVerification, requestPasswordReset, resetPassword } from "../services/accountApi.ts";

/**
 * The account dialog, kept out of the mission shell.
 *
 * It is a modal: nothing in it renders until someone clicks "Sign in", "Create account" or an
 * account link, and it drags the whole account service module behind it. The mission shell is the
 * entry chunk and has a 240 kB budget, so a dialog nobody has opened does not belong in it.
 */
export default function AuthDialog({ token: initialToken = "", mode, onModeChange, onClose, onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(initialToken);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const credentials = mode === "login" || mode === "register";
  const heading = {
    login: "Sign in",
    register: "Create account",
    forgot: "Reset your password",
    reset: "Choose a new password",
    verify: "Verify your email address",
  }[mode] || "Account access";

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (credentials) {
        onAuthenticated(await authenticate(mode, email, password));
        return;
      }
      if (mode === "forgot") {
        const response = await requestPasswordReset(email.trim());
        setMessage(
          response.debugToken
            ? `No mail server is configured on this development server, so here is the reset token directly: ${response.debugToken}`
            : "If that address has an account, a reset link is on its way. The link works once and expires shortly.",
        );
        return;
      }
      if (mode === "reset") {
        const response = await resetPassword(token.trim(), password);
        clearSession();
        setMessage(`${response.note} You can sign in with the new password now.`);
        setPassword("");
        return;
      }
      if (mode === "verify") {
        await confirmVerification(token.trim());
        setMessage("Email address verified. This browser will show the new status after you sign in again.");
        return;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4" role="dialog" aria-modal="true" aria-label="Account access">
    <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded border border-line bg-space-900 p-5 shadow-2xl">
      <div className="flex items-center justify-between"><h2 className="text-lg text-slate-100">{heading}</h2><button type="button" className="icon-button" onClick={onClose}>Close</button></div>
      <p className="text-xs text-slate-400">Public science tools remain available without an account. Accounts protect saved scenarios.</p>
      {(mode === "login" || mode === "register" || mode === "forgot") && (
        <label className="block text-xs text-slate-300">Email<input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded border border-line-strong bg-space-950 p-2" /></label>
      )}
      {(credentials || mode === "reset") && (
        <label className="block text-xs text-slate-300">{mode === "reset" ? "New password" : "Password"}<input required minLength="12" type="password" autoComplete={credentials ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded border border-line-strong bg-space-950 p-2" /></label>
      )}
      {(mode === "reset" || mode === "verify") && (
        <label className="block text-xs text-slate-300">Link token<input required value={token} onChange={(e) => setToken(e.target.value)} className="mt-1 w-full rounded border border-line-strong bg-space-950 p-2 font-mono text-[11px]" placeholder="Paste the token from your email" /></label>
      )}
      {mode === "reset" && <p className="text-xs text-slate-400">Every session signed in with the old password stops working as soon as you submit.</p>}
      {mode === "verify" && <p className="text-xs text-slate-400">Verification records that the address is yours. It does not lock you out of anything.</p>}
      {error && <p className="text-xs text-warn" role="alert">{error}</p>}
      {message && <p className="text-xs text-slate-200" role="status">{message}</p>}
      <button disabled={busy} className="primary-button" type="submit">
        {busy ? "Working…" : heading}
      </button>
      {mode === "login" && (
        <button type="button" className="text-xs text-accent" onClick={() => { setError(""); setMessage(""); onModeChange("forgot"); }}>
          Forgot your password?
        </button>
      )}
      {mode === "forgot" && (
        <button type="button" className="text-xs text-accent" onClick={() => { setError(""); setMessage(""); onModeChange("login"); }}>
          Back to sign in
        </button>
      )}
      {credentials && (
        <button type="button" className="text-xs text-accent" onClick={() => { setError(""); setMessage(""); onModeChange(mode === "login" ? "register" : "login"); }}>
          {mode === "login" ? "Create account" : "I already have an account"}
        </button>
      )}
      <button type="button" className="text-xs text-accent" onClick={() => { setError(""); onClose(); }}>Cancel</button>
    </form>
  </div>;
}
