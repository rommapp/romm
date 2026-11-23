import { describe, expect, it } from "vitest";
import { nextSortDir } from "./nextSortDir";

describe("nextSortDir", () => {
  it("flips the active column", () => {
    expect(nextSortDir(true, "asc")).toBe("desc");
    expect(nextSortDir(true, "desc")).toBe("asc");
  });

  it("starts any other column ascending", () => {
    expect(nextSortDir(false, "asc")).toBe("asc");
    expect(nextSortDir(false, "desc")).toBe("asc");
  });
});
