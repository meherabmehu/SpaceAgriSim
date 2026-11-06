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
export function Limitations({ items }) {
  return (
    <div className="warning-box">
      {(items || []).map((item, i) => (
        <p key={i}>{item}</p>
      ))}
    </div>
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
