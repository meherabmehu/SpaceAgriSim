import { useEffect, useRef, useState } from "react";
import { api, isAbortError } from "../../services/platformApi.ts";

// Stable identities, so returning one of them cannot cause a render loop in a consumer effect.
const PENDING = { data: null, error: "", loading: true };
const SKIPPED = { data: null, error: "", loading: false };

// A fast slider hands the hook a new parameter set on every keystroke; without this the panel
// would issue one request per intermediate value. The debounce collapses them into one.
const DEBOUNCE_MS = 150;

/**
 * One API resource, as a React state machine that cannot show the wrong answer.
 *
 * Three properties are load-bearing, and each of them was broken at some point:
 *
 *  1. **A resource that was never asked for makes no request.** `path` of `null` means the caller
 *     is gating an authenticated resource on a session that does not exist; it used to be passed
 *     to `api()`, whose URL template produced `GET /apinull`.
 *
 *  2. **A superseded response can never be committed.** Every request carries an identity, and
 *     only the newest identity may write state. `AbortController` alone is not enough: it cancels
 *     a request that is still in flight, but it cannot un-resolve one whose body has already
 *     arrived - the bytes are in memory, `fetch` resolved before the abort, and the `.then` that
 *     follows will run. That window is small in wall-clock terms and trivially reachable in
 *     practice (a 2 kB JSON reply is buffered in one packet), and the failure it produces is a
 *     panel showing the previous parameters' numbers underneath the new controls.
 *
 *  3. **A cancellation is not a failure.** Aborting a request is something *this hook* did on
 *     purpose. It must never reach the user as an error banner, and it must never be mistaken for
 *     a completed load with no data.
 *
 * The returned value is also derived from the request key rather than only from committed state,
 * so the very render in which the parameters change already reports "loading" instead of handing
 * the caller the previous parameters' data under the new controls.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useResource(path, body) {
  const bodyKey = JSON.stringify(body);
  const enabled = typeof path === "string" && path.length > 0;
  // Identity of the requested resource. `\u0000` cannot appear in either half, so two different
  // (path, body) pairs cannot collide into one key.
  const requestKey = enabled ? `${path}\u0000${bodyKey ?? ""}` : "";
  // Identity of the newest request this hook has started. Only a request holding the newest
  // identity may commit.
  const newest = useRef(0);
  // The identity travels *beside* the state, not inside it: consumers must keep receiving exactly
  // `{ data, error, loading }`, and the state object keeps its identity until it is replaced.
  const [committed, setCommitted] = useState({ requestKey: "", state: PENDING });

  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    const requestId = newest.current + 1;
    newest.current = requestId;
    // `cancelled` covers unmount, where no newer request exists to advance the identity.
    let cancelled = false;
    const isCurrent = () => !cancelled && newest.current === requestId;

    const timer = setTimeout(() => {
      api(path, bodyKey === undefined ? undefined : JSON.parse(bodyKey), controller.signal)
        .then((data) => {
          if (isCurrent())
            setCommitted({ requestKey, state: { data, error: "", loading: false } });
        })
        .catch((error) => {
          if (!isCurrent() || isAbortError(error)) return;
          setCommitted({
            requestKey,
            state: {
              data: null,
              error: error instanceof Error ? error.message : String(error),
              loading: false,
            },
          });
        });
    }, DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      controller.abort();
    };
  }, [path, bodyKey, enabled, requestKey]);

  if (!enabled) return SKIPPED;
  // Committed state belongs to the request key it was fetched for. If the key has moved on - or
  // nothing has been committed for it yet - the honest answer is "still loading", never the
  // previous resource's data.
  return committed.requestKey === requestKey ? committed.state : PENDING;
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
