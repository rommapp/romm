import { describe, expect, it } from "vitest";
import { transportLooksDegraded } from "./index";

describe("transportLooksDegraded", () => {
  it("treats polling as degraded", () => {
    expect(transportLooksDegraded("polling")).toBe(true);
  });

  it("treats websocket as healthy", () => {
    expect(transportLooksDegraded("websocket")).toBe(false);
  });

  it("treats missing transport as healthy", () => {
    expect(transportLooksDegraded(undefined)).toBe(false);
  });
});
