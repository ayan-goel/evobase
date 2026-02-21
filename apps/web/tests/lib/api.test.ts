import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

const mockGetSession = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: mockGetSession,
    },
  }),
}));

describe("apiFetch (client)", () => {
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
      data: {
        session: { access_token: "test-token-123" },
      },
    });

    let capturedHeaders: HeadersInit | undefined;
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ repos: [], count: 0 }),
      });
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api");
    await getRepos();

    expect(capturedHeaders).toEqual(
      expect.objectContaining({
        Authorization: "Bearer test-token-123",
      }),
    );
  });

  it("redirects to /login on 401 response", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: "expired-token" } },
    });

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: () => Promise.resolve("Unauthorized"),
    }) as unknown as typeof fetch;

    const hrefSetter = vi.fn();
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
      configurable: true,
    });
    Object.defineProperty(window.location, "href", {
      set: hrefSetter,
      get: () => "",
      configurable: true,
    });

    const { getRepos } = await import("@/lib/api");
    await expect(getRepos()).rejects.toThrow("Unauthorized");
    expect(hrefSetter).toHaveBeenCalledWith("/login");
  });

  it("works without session for unauthenticated context", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: null },
    });

    let capturedHeaders: Record<string, string> | undefined;
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ repos: [], count: 0 }),
      });
    }) as unknown as typeof fetch;

    const { getRepos } = await import("@/lib/api");
    await getRepos();

    expect(capturedHeaders?.Authorization).toBeUndefined();
  });

  it("handles 204 No Content responses (delete endpoint)", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: "test-token-123" } },
    });

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: { get: (_key: string) => null },
      json: () => Promise.reject(new Error("No JSON body")),
      text: () => Promise.resolve(""),
    }) as unknown as typeof fetch;

    const { deleteRepo } = await import("@/lib/api");
    await expect(deleteRepo("repo-1")).resolves.toBeUndefined();
  });
});
