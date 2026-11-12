import { vi } from "vitest";

/**
 * A `fetch` stand-in whose every response is released by the test.
 *
 * Shared by the unit tests that pin request lifecycles. The point is ordering: a promise that only
 * the test resolves can be delivered before or after an `AbortController` fires, which is exactly
 * the distinction a network stub based on `setTimeout` (or a real server) cannot control. Anything
 * that needs to prove "this response must not be committed" needs this.
 */

function abortError() {
  return new DOMException("The operation was aborted.", "AbortError");
}

export function createFetchHarness() {
  const calls = [];
  const fetch = vi.fn((url, init = {}) => {
    let settle;
    let fail;
    const pending = new Promise((resolve, reject) => {
      settle = resolve;
      fail = reject;
    });
    const call = {
      url,
      init,
      signal: init.signal,
      /** Deliver a complete response with the given status and JSON body. */
      respond(status, payload) {
        settle({
          ok: status >= 200 && status < 300,
          status,
          json: async () => payload,
        });
      },
      /** Deliver a response whose body read is cancelled mid-stream. */
      respondThenCancelBody(status) {
        settle({
          ok: status >= 200 && status < 300,
          status,
          json: async () => {
            throw abortError();
          },
        });
      },
    };
    calls.push(call);
    if (init.signal) {
      if (init.signal.aborted) fail(abortError());
      else init.signal.addEventListener("abort", () => fail(abortError()));
    }
    return pending;
  });

  return {
    fetch,
    calls,
    /** The first request whose URL contains `fragment`. */
    callTo(fragment) {
      const found = calls.find((call) => String(call.url).includes(fragment));
      if (!found) throw new Error(`no request containing ${fragment} was issued`);
      return found;
    },
    /** Every request whose URL contains `fragment`. */
    callsTo(fragment) {
      return calls.filter((call) => String(call.url).includes(fragment));
    },
  };
}
