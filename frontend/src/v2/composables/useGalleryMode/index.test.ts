import { describe, expect, it } from "vitest";
import {
  GROUP_BY_MODES,
  isGroupByMode,
  orderKeyForGroupBy,
  resolveGroupBy,
} from "./index";

describe("isGroupByMode", () => {
  it("accepts every mode the toolbar can offer", () => {
    expect(GROUP_BY_MODES.every((mode) => isGroupByMode(mode))).toBe(true);
  });

  it("rejects anything else", () => {
    expect(isGroupByMode("decade")).toBe(false);
  });
});

// Letter buckets come from the server's char index, which only covers a
// lexically ordered result.
describe("resolveGroupBy", () => {
  it("keeps letter buckets on a lexical axis", () => {
    expect(resolveGroupBy("letter", "name")).toBe("letter");
    expect(resolveGroupBy("letter", "fs_name")).toBe("letter");
  });

  it("reads as flat on an axis the server cannot index", () => {
    expect(resolveGroupBy("letter", "fs_size_bytes")).toBe("none");
    expect(resolveGroupBy("letter", "last_played")).toBe("none");
  });

  // Platform-only modes group client-side, so the axis has no say.
  it("leaves the other modes alone", () => {
    expect(resolveGroupBy("family", "fs_size_bytes")).toBe("family");
  });
});

describe("orderKeyForGroupBy", () => {
  it("snaps a non-lexical axis to the default when letters are picked", () => {
    expect(orderKeyForGroupBy("letter", "average_rating")).toBe("name");
  });

  it("keeps an axis that already carries letters", () => {
    expect(orderKeyForGroupBy("letter", "fs_name")).toBe("fs_name");
  });

  it("keeps the axis for every other mode", () => {
    expect(orderKeyForGroupBy("none", "average_rating")).toBe("average_rating");
  });
});
