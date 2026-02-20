import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

const mockGetSession = vi.fn();

vi.mock("@/lib/supabase/server", () => ({
  createClient: () =>
    Promise.resolve({
      auth: {
        getSession: mockGetSession,
      },
    }),
}));

describe("apiFetch (server)", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    vi.resetModules();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("attaches bearer token when session exists", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: "server-token-456" } },
    });

    let capturedHeaders: HeadersInit | undefined;
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ repos: [], count: 0 }),
      });
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api-server");
    await getRepos();

    expect(capturedHeaders).toEqual(
      expect.objectContaining({
        Authorization: "Bearer server-token-456",
      }),
    );
  });

  it("sends no Authorization header when session is absent", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    let capturedHeaders: Record<string, string> | undefined;
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ repos: [], count: 0 }),
      });
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api-server");
    await getRepos();

    expect(capturedHeaders?.Authorization).toBeUndefined();
  });

  it("sets cache: no-store on every request", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    let capturedInit: RequestInit | undefined;
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedInit = init;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ repos: [], count: 0 }),
      });
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api-server");
    await getRepos();

    expect(capturedInit?.cache).toBe("no-store");
  });

  it("throws an API error on non-ok responses", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Internal Server Error"),
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api-server");
    await expect(getRepos()).rejects.toThrow("API 500");
  });

  it("throws an API error on 401 instead of redirecting", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: () => Promise.resolve("Unauthorized"),
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api-server");
    await expect(getRepos()).rejects.toThrow("API 401");
  });

  it("sends no Authorization header when getSession throws", async () => {
    mockGetSession.mockRejectedValue(new Error("cookies unavailable"));

    let capturedHeaders: Record<string, string> | undefined;
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ repos: [], count: 0 }),
      });
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api-server");
    await getRepos();

    expect(capturedHeaders?.Authorization).toBeUndefined();
  });
});
