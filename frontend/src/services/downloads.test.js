import { afterEach, describe, expect, it, vi } from "vitest";
import { filenameFromDisposition, postForFile } from "./downloads.ts";

/**
 * The download path, pinned where a browser test cannot see it.
 *
 * Two things went wrong here before. The filename was written on the client - `spaceagrisim-mission.`
 * plus the format - so a PDF built from one configuration arrived under a name that knew nothing
 * about it, while the server was sending a name that did. And a rejected request was saved as a
 * file anyway: `fetch` resolves on 422 exactly as it does on 200, so a blob of
 * `{"error": "..."}` was downloaded as `report.pdf` and announced as success.
 *
 * `fetch` is stubbed and `URL.createObjectURL`/anchor clicks are captured, so these tests assert
 * what the user's browser would have been told to save.
 */

function stubDownload(bytes = new Uint8Array([1, 2, 3])) {
  const clicked = [];
  const createObjectURL = vi.fn(() => "blob:test");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
  const originalCreate = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation((tag, ...rest) => {
    const element = originalCreate(tag, ...rest);
    if (tag === "a") {
      element.click = () => clicked.push({ download: element.download, href: element.href });
    }
    return element;
  });
  return { clicked, createObjectURL, revokeObjectURL, bytes };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("filenameFromDisposition", () => {
  it("takes the quoted filename the server sent", () => {
    expect(
      filenameFromDisposition(
        'attachment; filename="spaceagrisim-cea-wheat-co2Ppm-ambient-20261113.csv"',
        "fallback.csv",
      ),
    ).toBe("spaceagrisim-cea-wheat-co2Ppm-ambient-20261113.csv");
  });

  it("accepts an unquoted filename", () => {
    expect(filenameFromDisposition("attachment; filename=report.pdf", "fallback.pdf")).toBe(
      "report.pdf",
    );
  });

  it("prefers the RFC 5987 form when both are present", () => {
    expect(
      filenameFromDisposition(
        "attachment; filename=\"plain.csv\"; filename*=UTF-8''caf%C3%A9%20report.csv",
        "fallback.csv",
      ),
    ).toBe("café report.csv");
  });

  it("falls back when a proxy stripped the header", () => {
    expect(filenameFromDisposition(null, "spaceagrisim-mission.pdf")).toBe(
      "spaceagrisim-mission.pdf",
    );
    expect(filenameFromDisposition("attachment", "spaceagrisim-mission.csv")).toBe(
      "spaceagrisim-mission.csv",
    );
  });

  it("falls back rather than throwing on a malformed escape", () => {
    expect(
      filenameFromDisposition("attachment; filename*=UTF-8''%E0%A4%A", "fallback.csv"),
    ).toBe("fallback.csv");
  });
});

describe("postForFile", () => {
  it("saves the body under the server's filename and reports what it wrote", async () => {
    const harness = stubDownload();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers({
          "Content-Disposition": 'attachment; filename="spaceagrisim-mission.pdf"',
        }),
        blob: async () => new Blob([harness.bytes]),
      })),
    );

    const result = await postForFile("/reports/pdf", { crop: "lettuce" }, "fallback.pdf");
    expect(result.filename).toBe("spaceagrisim-mission.pdf");
    expect(result.bytes).toBeGreaterThan(0);
    expect(harness.clicked).toEqual([
      { download: "spaceagrisim-mission.pdf", href: "blob:test" },
    ]);
  });

  it("throws the server's message on a 422 and downloads nothing", async () => {
    const harness = stubDownload();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        headers: new Headers(),
        json: async () => ({ error: "validation_error", message: "band 'low' does not exist" }),
      })),
    );

    await expect(postForFile("/workflows/export", {}, "fallback.csv")).rejects.toThrow(
      "band 'low' does not exist",
    );
    expect(harness.clicked).toEqual([]);
  });

  it("refuses to save an empty response as a file", async () => {
    const harness = stubDownload();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: new Headers(),
        blob: async () => new Blob([]),
      })),
    );

    await expect(postForFile("/reports/csv", {}, "fallback.csv")).rejects.toThrow(/empty/i);
    expect(harness.clicked).toEqual([]);
  });
});
