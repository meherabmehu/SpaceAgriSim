import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFetchHarness } from "../../testSupport/deferredFetch.js";
import { RequestState, useResource } from "./moduleSupport.jsx";

/**
 * Regression tests for the resource hook's lifecycle.
 *
 * These exist because the defect they cover lives in the microtask queue. A superseded request can
 * resolve *before* the effect cleanup that aborts it runs - the response is already in memory when
 * `abort()` fires, so the abort cannot reject it - and the `.then` that follows then wrote the
 * previous parameters' payload into the component. In a browser that window is a packet of luck; a
 * Playwright suite cannot schedule it. Here the response body is released from a promise the test
 * itself controls, so the ordering is exact and the same on every run.
 *
 * `fetch` is stubbed rather than `api()`, on purpose: the real service layer runs, so these tests
 * also pin down what `api()` does with a cancellation (it must reject, not resolve to `null`).
 */

const DEBOUNCE_MS = 150;

let harness;

function Probe({ path, body }) {
  const state = useResource(path, body);
  return (
    <output data-testid="state">
      {JSON.stringify({ data: state.data, error: state.error, loading: state.loading })}
    </output>
  );
}

/** The state the hook handed its consumer on the last render. */
function state() {
  const node = view.container.querySelector("output");
  return JSON.parse(node.textContent);
}

/** Let the effect's timer fire, then let every promise chain it started settle. */
async function advance(ms = DEBOUNCE_MS) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await flush();
}

/** Drain the microtask queue without moving the clock. */
async function flush() {
  await act(async () => {
    for (let tick = 0; tick < 8; tick += 1) await Promise.resolve();
  });
}

/** Re-render with new props, synchronously running the effect cleanup. */
function rerender(element) {
  act(() => {
    view.rerender(element);
  });
}

let view;

beforeEach(() => {
  harness = createFetchHarness();
  vi.stubGlobal("fetch", harness.fetch);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function mount(element) {
  view = render(element);
  return view;
}

describe("useResource", () => {
  it("never requests a resource the caller gated off", async () => {
    mount(<Probe path={null} body={undefined} />);
    await advance(500);
    expect(harness.fetch).not.toHaveBeenCalled();
    expect(state()).toEqual({ data: null, error: "", loading: false });
  });

  it("keeps the skipped state identity stable across renders", () => {
    // A fresh object per render makes the state a new value every time, so any consumer effect
    // keyed on it re-fires forever.
    const seen = [];
    function Tracker({ path }) {
      seen.push(useResource(path));
      return <output>probe</output>;
    }
    const { container, rerender: again } = render(<Tracker path={null} />);
    again(<Tracker path={null} />);
    again(<Tracker path={null} />);
    expect(seen.length).toBe(3);
    expect(seen[1]).toBe(seen[0]);
    expect(seen[2]).toBe(seen[0]);
    container.remove();
  });

  it("keeps the pending state identity stable across renders", () => {
    const seen = [];
    function Tracker({ body }) {
      seen.push(useResource("/compare", body));
      return <output>probe</output>;
    }
    const { container, rerender: again } = render(<Tracker body={{ lightScale: 1 }} />);
    again(<Tracker body={{ lightScale: 2 }} />);
    expect(seen.map((state) => state.loading)).toEqual([true, true]);
    expect(seen[1]).toBe(seen[0]);
    container.remove();
  });

  it("coalesces a burst of parameter changes into one request", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance(100);
    rerender(<Probe path="/compare" body={{ lightScale: 1.5 }} />);
    await advance(100);
    rerender(<Probe path="/compare" body={{ lightScale: 2 }} />);
    await advance();
    expect(harness.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(harness.calls[0].init.body)).toEqual({ lightScale: 2 });
  });

  it("does not re-request when a re-render passes an equal body", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 2 }} />);
    await advance();
    expect(harness.fetch).toHaveBeenCalledTimes(1);
    // A parent that rebuilds the same object on every render must not start a request loop.
    rerender(<Probe path="/compare" body={{ lightScale: 2 }} />);
    await advance(500);
    expect(harness.fetch).toHaveBeenCalledTimes(1);
  });

  it("reports loading, not the previous payload, as soon as the parameters change", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    harness.calls[0].respond(200, { ratio: 1 });
    await flush();
    expect(state()).toEqual({ data: { ratio: 1 }, error: "", loading: false });

    rerender(<Probe path="/compare" body={{ lightScale: 2 }} />);
    // Before the new request has even been issued: the old numbers are for the old parameters and
    // must not be on screen underneath the new control.
    expect(state()).toEqual({ data: null, error: "", loading: true });
  });

  it("ignores a response that lands after the parameters changed", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    const first = harness.calls[0];

    // The stale response is *already delivered* to `fetch` - the abort that follows cannot reject
    // it, which is exactly the hole the abort-only implementation left open.
    first.respond(200, { ratio: 1 });

    rerender(<Probe path="/compare" body={{ lightScale: 2 }} />);
    await flush();

    // The stale `.then` has now run. It must not have committed anything.
    expect(state()).toEqual({ data: null, error: "", loading: true });
    expect(first.signal.aborted).toBe(true);

    await advance();
    harness.calls[1].respond(200, { ratio: 2 });
    await flush();
    expect(state()).toEqual({ data: { ratio: 2 }, error: "", loading: false });
    expect(harness.fetch).toHaveBeenCalledTimes(2);
  });

  it("honours out-of-order delivery when the newer request answers first", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    rerender(<Probe path="/compare" body={{ lightScale: 2 }} />);
    await advance();
    expect(harness.fetch).toHaveBeenCalledTimes(2);

    harness.calls[1].respond(200, { ratio: 2 });
    await flush();
    expect(state()).toEqual({ data: { ratio: 2 }, error: "", loading: false });

    // The older response arrives late; it belongs to parameters that are no longer on screen.
    harness.calls[0].respond(200, { ratio: 1 });
    await flush();
    expect(state()).toEqual({ data: { ratio: 2 }, error: "", loading: false });
  });

  it("treats a cancellation as a cancellation, never as an error", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    rerender(<Probe path="/compare" body={{ lightScale: 2 }} />);
    await flush();
    expect(harness.calls[0].signal.aborted).toBe(true);
    expect(state().error).toBe("");
    expect(state().loading).toBe(true);
  });

  it("treats a cancelled body read as a cancellation, not as an empty result", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    harness.calls[0].respondThenCancelBody(200);
    await flush();
    // A resolved `null` here would have been committed as "loaded successfully, no data".
    expect(state()).toEqual({ data: null, error: "", loading: true });
  });

  it("surfaces the server's message when a request genuinely fails", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    harness.calls[0].respond(500, { detail: "comparison unavailable" });
    await flush();
    expect(state()).toEqual({ data: null, error: "comparison unavailable", loading: false });
  });

  it("falls back to the status line when the failure body is not JSON", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    harness.calls[0].respond(503, null);
    await flush();
    expect(state().error).toBe("API request failed (503)");
    expect(state().loading).toBe(false);
  });

  it("cancels an in-flight request on unmount and commits nothing afterwards", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    const request = harness.calls[0];
    act(() => {
      view.unmount();
    });
    expect(request.signal.aborted).toBe(true);
    // A response that lands after the owner is gone must be a no-op, not a state write.
    request.respond(200, { ratio: 1 });
    await expect(flush()).resolves.toBeUndefined();
  });

  it("does not issue a request at all when it unmounts inside the debounce window", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    act(() => {
      view.unmount();
    });
    await advance(1000);
    expect(harness.fetch).not.toHaveBeenCalled();
  });

  it("starts fresh on remount instead of reusing the previous mount's result", async () => {
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    await advance();
    harness.calls[0].respond(200, { ratio: 1 });
    await flush();
    expect(state().data).toEqual({ ratio: 1 });

    act(() => {
      view.unmount();
    });
    mount(<Probe path="/compare" body={{ lightScale: 1 }} />);
    expect(state()).toEqual({ data: null, error: "", loading: true });

    await advance();
    expect(harness.fetch).toHaveBeenCalledTimes(2);
    harness.calls[1].respond(200, { ratio: 3 });
    await flush();
    expect(state().data).toEqual({ ratio: 3 });
  });
});

describe("RequestState", () => {
  it("shows a skeleton while a primary resource loads", () => {
    const { container } = render(
      <RequestState state={{ data: null, error: "", loading: true }} />,
    );
    expect(container.textContent).toContain("Loading verified API output");
  });

  it("stays quiet while a secondary resource loads", () => {
    const { container } = render(
      <RequestState state={{ data: null, error: "", loading: true }} secondary />,
    );
    expect(container.textContent).toBe("");
  });

  it("still reports a secondary resource that failed", () => {
    const { container } = render(
      <RequestState state={{ data: null, error: "verdict unavailable", loading: false }} secondary />,
    );
    expect(container.textContent).toContain("verdict unavailable");
  });
});
