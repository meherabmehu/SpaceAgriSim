import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFetchHarness } from "../../testSupport/deferredFetch.js";
import { ScientificWorkflow } from "./ScientificWorkflow.jsx";

/**
 * Component-level regression tests for request lifecycles.
 *
 * The hook tests next to this file prove the general rule. These cover the two panels that issue a
 * request from their own effect rather than through the hook, because the rule has to hold there
 * too - a cancelled request must not be reported as an empty result.
 */

let harness;
let view;

function text() {
  return view.container.textContent;
}

async function advance(ms = 150) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await flush();
}

async function flush() {
  await act(async () => {
    for (let tick = 0; tick < 8; tick += 1) await Promise.resolve();
  });
}

function rerender(element) {
  act(() => {
    view.rerender(element);
  });
}

const SAVED_LIST = {
  analyses: [
    {
      id: "a1",
      title: "Salinity stress run",
      modelId: "mizuna-microbial-relative-load-v2",
      createdAt: "2026-01-01T00:00:00Z",
    },
  ],
  pagination: { total: 1 },
  usage: { count: 1, maxCount: 50 },
};

const noop = () => undefined;

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

describe("ScientificWorkflow saved analyses", () => {
  it("keeps the list on screen when a re-read cancels the request it supersedes", async () => {
    view = render(
      <ScientificWorkflow session={{ token: "a" }} onRequireSignIn={noop} setNotice={noop} />,
    );
    await advance();
    harness.callTo("/workflow/models").respond(200, { models: [] });
    harness.callTo("/analyses?limit=5").respond(200, SAVED_LIST);
    await flush();
    expect(text()).toContain("Salinity stress run");

    // Saving an analysis re-runs this effect, and saving twice in quick succession makes the
    // second read supersede a *pending* first one: the abort fires while the list on screen is
    // still the previous answer. Reporting that cancellation as an empty result removed the panel
    // and left the reader looking at an account with nothing saved.
    rerender(
      <ScientificWorkflow session={{ token: "b" }} onRequireSignIn={noop} setNotice={noop} />,
    );
    await flush();
    rerender(
      <ScientificWorkflow session={{ token: "c" }} onRequireSignIn={noop} setNotice={noop} />,
    );
    await flush();

    expect(harness.callsTo("/analyses?limit=5").length).toBe(3);
    expect(text()).toContain("Salinity stress run");
  });

  it("does not show a rejected re-read as an empty account", async () => {
    view = render(
      <ScientificWorkflow session={{ token: "t" }} onRequireSignIn={noop} setNotice={noop} />,
    );
    await advance();
    harness.callTo("/workflow/models").respond(200, { models: [] });
    harness.callTo("/analyses?limit=5").respond(200, SAVED_LIST);
    await flush();
    expect(text()).toContain("Salinity stress run");

    rerender(<ScientificWorkflow session={{ token: "u" }} onRequireSignIn={noop} setNotice={noop} />);
    await flush();
    harness.callsTo("/analyses?limit=5").at(-1).respond(401, { detail: "session expired" });
    await flush();
    // A genuine failure may clear the panel; it must never leave a stale list claiming to be this
    // account's.
    expect(text()).not.toContain("Salinity stress run");
  });
});
