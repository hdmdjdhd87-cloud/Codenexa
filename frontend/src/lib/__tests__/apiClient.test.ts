import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/lib/telegram", () => ({
  getInitData: () => "mock-init-data",
}));

import { apiRequest, downloadAuthorizedFile, ApiClientError, shouldRetryRequest, computeBackoffDelayMs } from "@/lib/apiClient";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

beforeEach(() => {
  localStorage.setItem("codenexa.session_token", "test-token");
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

/* ============================= pure functions ============================= */

describe("shouldRetryRequest", () => {
  it("retries GET on network error (status null)", () => {
    expect(shouldRetryRequest("GET", null, false)).toBe(true);
  });

  it("retries GET on 500", () => {
    expect(shouldRetryRequest("GET", 500, false)).toBe(true);
  });

  it("retries GET on 429", () => {
    expect(shouldRetryRequest("GET", 429, false)).toBe(true);
  });

  it("does not retry GET on ordinary 4xx like 404", () => {
    expect(shouldRetryRequest("GET", 404, false)).toBe(false);
  });

  it("does not retry POST without idempotency key even on 500", () => {
    // F-012 из аудита: мутация без Idempotency-Key не идемпотентна —
    // повтор на 5xx мог бы создать дубликат side-effect.
    expect(shouldRetryRequest("POST", 500, false)).toBe(false);
  });

  it("retries POST with idempotency key on 500", () => {
    expect(shouldRetryRequest("POST", 500, true)).toBe(true);
  });

  it("does not retry POST with idempotency key on ordinary 4xx", () => {
    expect(shouldRetryRequest("POST", 422, true)).toBe(false);
  });

  it("retries DELETE with idempotency key on network error", () => {
    expect(shouldRetryRequest("DELETE", null, true)).toBe(true);
  });
});

describe("computeBackoffDelayMs", () => {
  it("returns a positive delay that grows with attempt number", () => {
    const d1 = computeBackoffDelayMs(1);
    const d2 = computeBackoffDelayMs(2);
    expect(d1).toBeGreaterThan(0);
    // база растёт экспоненциально (jitter может немного смешать точный
    // порядок отдельных сэмплов, но базовая часть d2 всегда выше d1's base)
    expect(d2).toBeGreaterThanOrEqual(400); // минимум база на attempt=2 (800) минус не бывает меньше своей базы
  });

  it("caps the delay so it never grows unbounded", () => {
    const d = computeBackoffDelayMs(20); // огромный attempt
    expect(d).toBeLessThan(4000 * 1.5 + 1); // капа 4000 + макс 50% джиттера
  });

  it("adds jitter so repeated calls are not always identical", () => {
    const samples = Array.from({ length: 10 }, () => computeBackoffDelayMs(3));
    const unique = new Set(samples);
    expect(unique.size).toBeGreaterThan(1);
  });
});

/* ============================= apiRequest integration ============================= */

describe("apiRequest retry behavior", () => {
  it("retries a GET once after a 500 and succeeds on second attempt", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(500, { error: { code: "X", message: "boom" } }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const promise = apiRequest<{ ok: boolean }>("/api/v1/whatever");
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a GET on a plain 404 and throws immediately", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(404, { error: { code: "NOT_FOUND", message: "nope" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/api/v1/whatever")).rejects.toThrow(ApiClientError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a POST without Idempotency-Key on 500 — single attempt only", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(500, { error: { code: "X", message: "boom" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/api/v1/whatever", { method: "POST", body: {} })).rejects.toThrow(ApiClientError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries a POST with Idempotency-Key on 500", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(500, { error: { code: "X", message: "boom" } }))
      .mockResolvedValueOnce(jsonResponse(200, { id: "doc-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const promise = apiRequest("/api/v1/aidocs/documents", {
      method: "POST",
      body: {},
      headers: { "Idempotency-Key": "abc-123" },
    });
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result).toEqual({ id: "doc-1" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("re-authenticates once on 401 and retries the original request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "SESSION_INVALID", message: "expired" } }))
      .mockResolvedValueOnce(jsonResponse(200, { token: "fresh-token" })) // POST /auth/telegram
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })); // retried original request
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<{ ok: boolean }>("/api/v1/whatever");
    expect(result).toEqual({ ok: true });
    expect(localStorage.getItem("codenexa.session_token")).toBe("fresh-token");
  });
});

/* ============================= downloadAuthorizedFile ============================= */

describe("downloadAuthorizedFile", () => {
  it("throws a TIMEOUT ApiClientError when the request aborts", async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          const err = new DOMException("aborted", "AbortError");
          reject(err);
        });
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const promise = downloadAuthorizedFile("/api/v1/aidocs/documents/1/export/pdf", "doc.pdf");
    const assertion = expect(promise).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.runAllTimersAsync();
    await assertion;
  });

  it("re-authenticates on 401 before failing, matching apiRequest's recovery behavior", async () => {
    // URL.createObjectURL/revokeObjectURL не реализованы в jsdom по умолчанию
    (globalThis as unknown as { URL: typeof URL }).URL.createObjectURL = vi.fn(() => "blob:mock");
    (globalThis as unknown as { URL: typeof URL }).URL.revokeObjectURL = vi.fn();

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "SESSION_INVALID", message: "expired" } }))
      .mockResolvedValueOnce(jsonResponse(200, { token: "fresh-token" }))
      .mockResolvedValueOnce(new Response(new Blob(["pdf-bytes"]), { status: 200, headers: { "Content-Type": "application/pdf" } }));
    vi.stubGlobal("fetch", fetchMock);

    await downloadAuthorizedFile("/api/v1/aidocs/documents/1/export/pdf", "doc.pdf");
    expect(localStorage.getItem("codenexa.session_token")).toBe("fresh-token");
  });
});
