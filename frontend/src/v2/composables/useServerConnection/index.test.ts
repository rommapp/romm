import { describe, expect, it } from "vitest";
import { shouldRefreshOnReconnect } from "./index";

describe("shouldRefreshOnReconnect", () => {
  it("refreshes only on a real reconnect (offline → online)", () => {
    expect(shouldRefreshOnReconnect(true, false)).toBe(true);
  });

  it("does not refresh on the initial reading (no prior state)", () => {
    expect(shouldRefreshOnReconnect(true, undefined)).toBe(false);
  });

  it("does not refresh while staying online", () => {
    expect(shouldRefreshOnReconnect(true, true)).toBe(false);
  });

  it("does not refresh when going offline", () => {
    expect(shouldRefreshOnReconnect(false, true)).toBe(false);
  });

  it("does not refresh while staying offline", () => {
    expect(shouldRefreshOnReconnect(false, false)).toBe(false);
  });
});
