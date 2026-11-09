import { useCallback, useEffect, useState } from "react";
import { Activity, KeyRound, ServerCog, ShieldCheck } from "lucide-react";
import { Card, number } from "../missionUI.jsx";

/**
 * Operator console.
 *
 * Reached by URL (`#operator`) rather than the sidebar: it is for whoever runs the deployment, not
 * for visitors. The token is kept in sessionStorage so closing the tab drops it, and the backend
 * answers 404 when no operator token is configured, which is what a public deployment will do.
 *
 * Everything shown here is aggregate or pseudonymous. The panel deliberately has no way to look up
 * an address: an operator needs to see that a deployment is healthy and whether someone is
 * behaving badly, not who anyone is.
 */

const STORAGE_KEY = "spaceagrisim.operator";
const base = import.meta.env.VITE_API_BASE_URL || "/api";

async function call(path, token) {
  const response = await fetch(`${base}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      body?.detail || body?.message || `Operator request failed (${response.status})`,
    );
  return body;
}

export function Operator() {
  const [token, setToken] = useState(() => sessionStorage.getItem(STORAGE_KEY) || "");
  const [summary, setSummary] = useState(null);
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (value) => {
    if (!value) return;
    setLoading(true);
    setError("");
    try {
      const [nextSummary, nextAudit] = await Promise.all([
        call("/admin/summary", value),
        call("/admin/audit?limit=100", value),
      ]);
      setSummary(nextSummary);
      setAudit(nextAudit);
      sessionStorage.setItem(STORAGE_KEY, value);
    } catch (err) {
      setSummary(null);
      setAudit(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // On mount, reuse a token typed in this tab. The state update happens when the fetch resolves,
  // not in the effect body, so this cannot cascade a render loop.
  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return undefined;
    let active = true;
    Promise.all([call("/admin/summary", stored), call("/admin/audit?limit=100", stored)])
      .then(([nextSummary, nextAudit]) => {
        if (!active) return;
        setSummary(nextSummary);
        setAudit(nextAudit);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const submit = (event) => {
    event.preventDefault();
    load(token.trim());
  };

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <ServerCog size={12} /> Operator console
        </span>
        <h2>Deployment health, without looking at anyone&apos;s account</h2>
        <p>
          This page is for whoever runs the deployment. It shows aggregate counts and pseudonymous
          events. It cannot look up an address, and without a configured operator token the API
          answers as if the page did not exist.
        </p>
      </div>

      <Card title="Operator token">
        <form onSubmit={submit} className="operator-token">
          <label htmlFor="operator-token">
            Bearer token from SPACEAGRISIM_ADMIN_TOKEN
          </label>
          <div className="operator-token-row">
            <input
              id="operator-token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="paste the operator token"
              autoComplete="off"
            />
            <button className="primary-button" type="submit" disabled={loading || !token.trim()}>
              <KeyRound size={14} /> {loading ? "Checking…" : "Open console"}
            </button>
          </div>
        </form>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        <p className="muted">
          Kept in this browser tab only. A wrong token and a missing token both answer 401, and a
          deployment with no operator token answers 404 for everything here.
        </p>
      </Card>

      {summary && (
        <>
          <div className="module-grid">
            <Card title="Service">
              <dl className="metric-list">
                <div>
                  <dt>Database</dt>
                  <dd>
                    {summary.database.status} · {summary.database.dialect}
                  </dd>
                </div>
                <div>
                  <dt>Durable storage</dt>
                  <dd>{summary.storage.durable ? "yes" : "no"}</dd>
                </div>
                <div>
                  <dt>Account email</dt>
                  <dd>{summary.emailDelivery}</dd>
                </div>
                <div>
                  <dt>Rate-limit identity</dt>
                  <dd>{summary.rateLimitIdentity}</dd>
                </div>
                <div>
                  <dt>Scientific status</dt>
                  <dd>{summary.scientificValidation}</dd>
                </div>
              </dl>
              {!summary.storage.durable && (
                <div className="warning-box">
                  <p>{summary.storage.remedy}</p>
                </div>
              )}
            </Card>

            <Card title="Usage">
              <dl className="metric-list">
                <div>
                  <dt>Accounts</dt>
                  <dd>{number(summary.accounts, 0)}</dd>
                </div>
                <div>
                  <dt>Live share links</dt>
                  <dd>{number(summary.liveShareLinks, 0)}</dd>
                </div>
                {Object.entries(summary.activityByKind || {}).map(([kind, count]) => (
                  <div key={kind}>
                    <dt>{kind}</dt>
                    <dd>{number(count, 0)}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>

          <Card title="Provenance re-sync" label="SCHEDULED JOB, NOT A LIVE QUERY">
            {summary.provenanceResync ? (
              <>
                <dl className="metric-list">
                  <div>
                    <dt>Last checked</dt>
                    <dd>{new Date(summary.provenanceResync.checkedAt).toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Studies checked</dt>
                    <dd>{summary.provenanceResync.studiesChecked}</dd>
                  </div>
                  {Object.entries(summary.provenanceResync.verdicts || {}).map(([verdict, count]) => (
                    <div key={verdict}>
                      <dt>{verdict}</dt>
                      <dd>{count}</dd>
                    </div>
                  ))}
                </dl>
                <p className="muted">
                  Run <code>python scripts/resync_osdr.py</code> on a schedule. A study whose bytes
                  or version changed is reported for a human to re-pin; the script never edits a
                  pin itself.
                </p>
              </>
            ) : (
              <p className="muted">
                No re-sync snapshot in this deployment's bundle. Run{" "}
                <code>python scripts/resync_osdr.py</code> and redeploy to publish one.
              </p>
            )}
          </Card>

          <Card title="Recent account events" action={<Activity size={16} />}>
            {audit && (
              <>
                <p className="muted">{audit.scope}</p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">When</th>
                        <th scope="col">Event</th>
                        <th scope="col">Account</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.events.map((event, index) => (
                        <tr key={`${event.at}-${index}`}>
                          <td>{new Date(event.at).toLocaleString()}</td>
                          <td>{event.kind}</td>
                          <td className="mono">{event.account}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="fine-print">
                  <ShieldCheck size={13} /> Account ids are one-way hashes: events can be
                  correlated without identifying anybody, and no address or payload is stored.
                </div>
              </>
            )}
          </Card>
        </>
      )}
    </>
  );
}
