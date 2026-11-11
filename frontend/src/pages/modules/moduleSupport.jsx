import { useEffect, useState } from "react";
import { api } from "../../services/platformApi.ts";

// The resolved state a resource reports when it was never asked for. A module-level constant keeps
// its identity stable, so a skipped resource cannot cause a render loop in a consumer effect.
const skipped = { data: null, error: "", loading: false };

// eslint-disable-next-line react-refresh/only-export-components
export function useResource(path, body) {
  const key = JSON.stringify(body);
  // A `null` path means "there is nothing to ask for yet" - the caller gates an authenticated
  // resource on a session that does not exist. It used to be handed straight to `api()`, whose
  // `${base}${path}` template produced the request `GET /apinull` (404 in every console, signed
  // out, on the account page). A skipped resource is resolved with no data and no error, so the
  // caller renders its own signed-out branch instead of a red banner.
  const enabled = typeof path === "string" && path.length > 0;
  const [state, setState] = useState({ data: null, error: "", loading: true });
  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setState({ data: null, error: "", loading: true });
      api(
        path,
        key === undefined ? undefined : JSON.parse(key),
        controller.signal,
      )
        .then((data) => setState({ data, error: "", loading: false }))
        .catch((err) => {
          if (err.name !== "AbortError")
            setState({ data: null, error: err.message, loading: false });
        });
    }, 150);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [path, key, enabled]);
  // A skipped resource reports "resolved, nothing to show" without touching state, so the effect
  // never sets state synchronously (that is a cascading render, and an ESLint error here).
  return enabled ? state : skipped;
}
/**
 * The visible state of one request.
 *
 * `secondary` is for a resource that annotates a page rather than being its subject (the external
 * validation verdict beside a model table, the closed-loop panel beside the benchmarks). Those used
 * to be rendered as `{data && <Panel/>}`, so a failed request removed the panel and left no trace -
 * which on this product means a failed *external* check could disappear from the page that exists to
 * show it. A secondary resource therefore stays quiet while it loads, and still says so when it
 * fails.
 */
export function RequestState({ state, secondary = false }) {
  return state.error ? (
    <div className="error-banner" role="alert">
      {state.error}
    </div>
  ) : state.loading && !secondary ? (
    <div className="skeleton" role="status">
      Loading verified API output…
    </div>
  ) : null;
}
/**
 * Evidence notes for a result.
 *
 * These used to render as a warning block on every page, which trained the reader to skip them and
 * made the whole workspace look like it was apologising. The lines are unchanged and still one
 * click away; what changed is that they no longer compete with the result for attention.
 */
export function Limitations({ items, title = "Evidence notes" }) {
  const notes = (items || []).filter(Boolean);
  if (!notes.length) return null;
  return (
    <details className="evidence-note">
      <summary>
        {title} <span className="muted">({notes.length})</span>
      </summary>
      <ul>
        {notes.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </details>
  );
}
export function JsonDetails({ title = "Inspect complete API output", data }) {
  return (
    <details className="details-block">
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}
