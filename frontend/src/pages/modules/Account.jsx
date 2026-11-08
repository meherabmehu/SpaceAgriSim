import { useCallback, useEffect, useState } from "react";
import { Activity, Copy, Link2, MailCheck, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { Card, number } from "../missionUI.jsx";
import { readSession } from "../../services/auth.ts";
import {
  activityLabels,
  createShareLink,
  fetchActivity,
  revokeShareLinks,
  requestVerification,
  shareUrl,
} from "../../services/accountApi.ts";
import { useResource, RequestState, JsonDetails } from "./moduleSupport.jsx";

/**
 * Account, sharing and deployment-truth panel.
 *
 * Three things live here because they answer the same question — "can I trust this deployment
 * with my work?" — and each one is easy for a hosted demo to answer dishonestly:
 *   · whether the address on the account is verified,
 *   · whether saved work survives a restart,
 *   · who can read a scenario once it is shared.
 */
export function Account({ onRequireSignIn }) {
  const [session, setSession] = useState(() => readSession());
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [shareLinks, setShareLinks] = useState({});
  const readiness = useResource("/ready");
  const scenarios = useResource(session ? "/scenarios" : null);

  useEffect(() => {
    const sync = () => setSession(readSession());
    window.addEventListener("storage", sync);
    const timer = setInterval(sync, 2000);
    return () => {
      window.removeEventListener("storage", sync);
      clearInterval(timer);
    };
  }, []);

  const run = useCallback(async (key, action) => {
    setBusy(key);
    setError("");
    setNotice("");
    try {
      setNotice(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }, []);

  const [events, setEvents] = useState(null);
  const loadActivity = useCallback(async () => {
    try {
      setEvents(await fetchActivity());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  // No synchronous setState here: the fetch resolves into state, and signing out simply stops
  // the request from being able to land.
  useEffect(() => {
    if (!session) return undefined;
    let active = true;
    fetchActivity()
      .then((data) => active && setEvents(data))
      .catch((err) => active && setError(err instanceof Error ? err.message : String(err)));
    return () => {
      active = false;
    };
  }, [session]);

  if (!session) {
    return (
      <>
        <div className="module-intro">
          <span className="pill">
            <UserRound size={12} /> Account
          </span>
          <h2>Sign in to manage a saved workspace</h2>
          <p>
            Every public science tool on this platform works without an account. An account adds
            saved scenarios, read-only share links and a security history for your own sign-ins.
          </p>
        </div>
        <Card title="Account features require sign-in">
          <p className="muted">
            Signing in is only needed for saved scenarios and sharing. The simulator, evidence
            panels and NASA dataset explorer stay open.
          </p>
          <button className="primary-button" type="button" onClick={onRequireSignIn}>
            Sign in or create an account
          </button>
        </Card>
      </>
    );
  }

  const saveShareLink = (scenarioId, name) =>
    run(`share-${scenarioId}`, async () => {
      const link = await createShareLink(scenarioId);
      setShareLinks((current) => ({
        ...current,
        [scenarioId]: { url: shareUrl(link.token), token: link.token },
      }));
      return `Read-only link created for “${name}”. It expires in ${link.expiresInDays} days and shows no account data.`;
    });

  const revoke = (scenarioId, name) =>
    run(`revoke-${scenarioId}`, async () => {
      const { revoked } = await revokeShareLinks(scenarioId);
      setShareLinks((current) => {
        const next = { ...current };
        delete next[scenarioId];
        return next;
      });
      return `${revoked} link${revoked === 1 ? "" : "s"} revoked for “${name}”. Anyone holding it now sees “not found”.`;
    });

  const verify = () =>
    run("verify", async () => {
      const response = await requestVerification(session.user.email);
      if (response.debugToken)
        return `Development server: no mail was sent. Verification token: ${response.debugToken}`;
      return `Verification link sent to ${session.user.email}.`;
    });

  const scenarioRows = scenarios.data?.scenarios || [];

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <UserRound size={12} /> Account &amp; sharing
        </span>
        <h2>Your account, your saved work, and what this deployment actually guarantees</h2>
        <p>
          Share links are read-only and carry no account data. Verification is recorded but never
          used to lock a working account out of its own scenarios.
        </p>
      </div>

      {(notice || error) && (
        <div className={error ? "error-banner" : "notice"} role={error ? "alert" : "status"}>
          {error || notice}
        </div>
      )}

      <div className="module-grid">
        <Card title="Signed in">
          <dl className="metric-list">
            <div>
              <dt>Address</dt>
              <dd>{session.user.email}</dd>
            </div>
            <div>
              <dt>Email verified</dt>
              <dd>{session.user.emailVerified ? "verified" : "not verified"}</dd>
            </div>
            <div>
              <dt>Session expires</dt>
              <dd>{new Date(session.expiresAt).toLocaleString()}</dd>
            </div>
          </dl>
          {!session.user.emailVerified && (
            <>
              <p className="muted">
                Verification lets the operator reach you about your account. It is not required to
                use the simulator, and it does not gate any scientific feature.
              </p>
              <button className="primary-button" type="button" disabled={busy === "verify"} onClick={verify}>
                <MailCheck size={14} /> {busy === "verify" ? "Requesting…" : "Send verification link"}
              </button>
            </>
          )}
        </Card>

        <Card title="Deployment guarantees">
          <RequestState state={readiness} />
          {readiness.data && (
            <>
              <dl className="metric-list">
                <div>
                  <dt>Storage</dt>
                  <dd>{readiness.data.storage.durable ? "durable" : "not durable"}</dd>
                </div>
                <div>
                  <dt>Database</dt>
                  <dd>{readiness.data.databaseDialect}</dd>
                </div>
                <div>
                  <dt>Account email</dt>
                  <dd>{readiness.data.emailDelivery}</dd>
                </div>
                <div>
                  <dt>Share links</dt>
                  <dd>{readiness.data.shareLinks ? "available" : "disabled"}</dd>
                </div>
                <div>
                  <dt>Rate-limit identity</dt>
                  <dd>{readiness.data.rateLimitIdentity}</dd>
                </div>
              </dl>
              <p className="muted">{readiness.data.storage.reason}</p>
              {!readiness.data.storage.durable && (
                <div className="warning-box">
                  <p>{readiness.data.storage.remedy}</p>
                </div>
              )}
              {readiness.data.emailDelivery === "outbox" && (
                <p className="muted">
                  This server has no SMTP configured, so account email is written to a development
                  outbox instead. Production refuses the request rather than pretending to send.
                </p>
              )}
              {readiness.data.emailDelivery === "unconfigured" && (
                <div className="warning-box">
                  <p>
                    Account email is unavailable: no SMTP is configured on this production server.
                    Verification and reset requests answer with an explicit error instead of a
                    false “sent”.
                  </p>
                </div>
              )}
              <p className="muted">
                Scientific status is unchanged by any of this: {readiness.data.scientificValidation}.
              </p>
            </>
          )}
        </Card>
      </div>

      <Card title="Saved scenarios and share links">
        <RequestState state={scenarios} />
        {!scenarios.loading && !scenarios.error && scenarioRows.length === 0 && (
          <p className="muted">
            No saved scenarios yet. Save one from the mission workspace footer, then share it here.
          </p>
        )}
        {scenarioRows.length > 0 && (
          <ul className="scenario-list">
            {scenarioRows.map((scenario) => (
              <li key={scenario.id}>
                <div>
                  <strong>{scenario.name}</strong>
                  <p className="muted">
                    {scenario.configuration?.crop} · {number(scenario.configuration?.simulationDays)} day
                    run · saved {new Date(scenario.createdAt).toLocaleDateString()}
                  </p>
                  {shareLinks[scenario.id] && (
                    <p className="share-url">
                      <code>{shareLinks[scenario.id].url}</code>
                      <button
                        type="button"
                        className="icon-button"
                        title="Copy link"
                        onClick={() => {
                          navigator.clipboard?.writeText(shareLinks[scenario.id].url);
                          setNotice("Share link copied to the clipboard.");
                        }}
                      >
                        <Copy size={13} />
                      </button>
                    </p>
                  )}
                </div>
                <div className="scenario-actions">
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busy === `share-${scenario.id}`}
                    onClick={() => saveShareLink(scenario.id, scenario.name)}
                  >
                    <Link2 size={13} /> {busy === `share-${scenario.id}` ? "Creating…" : "Share"}
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busy === `revoke-${scenario.id}`}
                    onClick={() => revoke(scenario.id, scenario.name)}
                  >
                    <Trash2 size={13} /> Revoke links
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Security history">
        <div className="card-actions">
          <button type="button" className="ghost-button" onClick={loadActivity}>
            <Activity size={13} /> Refresh
          </button>
        </div>
        {!events && <p className="muted">Loading your own sign-in and share events…</p>}
        {events && events.events.length === 0 && <p className="muted">No recorded events yet.</p>}
        {events && events.events.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Event</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {events.events.map((event, index) => (
                <tr key={`${event.createdAt}-${index}`}>
                  <td>{activityLabels[event.kind] || event.kind}</td>
                  <td>{new Date(event.createdAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="fine-print">
          <ShieldCheck size={13} /> This history belongs to your account only. It records event
          types and times — never your address, your IP, or anything you typed.
        </div>
        <JsonDetails title="Inspect account API output" data={{ activity: events, scenarios: scenarioRows }} />
      </Card>
    </>
  );
}
