import { describe, expect, it } from "vitest";
import { uuidv7 } from "./uuid";

describe("uuidv7", () => {
  it("encodes the time, version and variant", () => {
    const id = uuidv7(0x0192f1c47b2e);

    expect(id).toMatch(
      /^0192f1c4-7b2e-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });

  it("differs between calls in the same millisecond", () => {
    expect(uuidv7(1)).not.toBe(uuidv7(1));
  });
});
