import { describe, expect, it } from "vitest";
import { toError } from "./toError";

describe("toError", () => {
  it("returns an Error instance unchanged", () => {
    const err = Object.assign(new Error("boom"), { response: { status: 500 } });
    expect(toError(err)).toBe(err);
  });

  it("wraps a non-Error value in an Error with its string form", () => {
    const err = toError("offline");
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("offline");
  });
});
