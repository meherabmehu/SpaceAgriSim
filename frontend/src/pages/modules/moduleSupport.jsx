import { useEffect, useState } from "react";
import { api } from "../../services/platformApi.ts";
// eslint-disable-next-line react-refresh/only-export-components
export function useResource(path, body) {
  const key = JSON.stringify(body);
  const [state, setState] = useState({ data: null, error: "", loading: true });
  useEffect(() => {
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
  }, [path, key]);
  return state;
}
export function RequestState({ state }) {
  return state.error ? (
    <div className="error-banner" role="alert">
      {state.error}
    </div>
  ) : state.loading ? (
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
