import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import streamingApi from "@/services/api/streaming";

const post = vi.hoisted(() => vi.fn());

vi.mock("@/services/api", () => ({
  default: { post },
  keepaliveHeaders: () => ({}),
}));

describe("releaseSessionKeepalive", () => {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response());

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    fetchMock.mockClear();
  });

  it("names the container and the claim where URLSearchParams has no size", async () => {
    // Chrome 111-112 and Safari 16.4 are in .browserslistrc and predate it.
    vi.spyOn(URLSearchParams.prototype, "size", "get").mockReturnValue(
      undefined as unknown as number,
    );

    await streamingApi.releaseSessionKeepalive(
      "ps2",
      "WEBSTATION-DEV",
      "2026-09-17T12:00:00+00:00",
    );

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/streaming/sessions/ps2?container=WEBSTATION-DEV&claimed_at=2026-09-17T12%3A00%3A00%2B00%3A00",
    );
  });

  it("sends no query when there is nothing to name", async () => {
    await streamingApi.releaseSessionKeepalive("ps2");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/streaming/sessions/ps2");
  });
});

describe("saveAndExitKeepalive", () => {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response());

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockClear();
  });

  it("names the container and the claim it saves", async () => {
    await streamingApi.saveAndExitKeepalive(
      "ps2",
      0,
      "WEBSTATION-DEV",
      "2026-09-17T12:00:00+00:00",
    );

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/streaming/sessions/ps2/save-and-exit?container=WEBSTATION-DEV&claimed_at=2026-09-17T12%3A00%3A00%2B00%3A00",
    );
  });
});

describe("saveAndExit", () => {
  beforeEach(() => {
    post.mockReset();
  });

  it("names the container and the claim it saves", async () => {
    await streamingApi.saveAndExit(
      "ps2",
      0,
      true,
      "WEBSTATION-DEV",
      "2026-09-17T12:00:00+00:00",
    );

    expect(post).toHaveBeenCalledWith(
      "/streaming/sessions/ps2/save-and-exit",
      { slot: 0, wait: true },
      {
        params: {
          container: "WEBSTATION-DEV",
          claimed_at: "2026-09-17T12:00:00+00:00",
        },
      },
    );
  });
});
