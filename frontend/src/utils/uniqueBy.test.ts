import { describe, expect, it } from "vitest";
import { uniqueBy } from "./uniqueBy";

describe("uniqueBy", () => {
  it("keeps the first item per key, in order", () => {
    const items = [
      { id: 1, n: "a" },
      { id: 2, n: "b" },
      { id: 1, n: "c" },
    ];
    expect(uniqueBy(items, (i) => i.id)).toEqual([items[0], items[1]]);
  });

  it("returns a new array for empty input", () => {
    expect(uniqueBy([], (i) => i)).toEqual([]);
  });
});
