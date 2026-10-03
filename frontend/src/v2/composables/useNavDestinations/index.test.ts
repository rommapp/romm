import { describe, expect, it } from "vitest";
import { navDestinationAt } from "./index";

describe("navDestinationAt", () => {
  it.each([
    ["/", "home"],
    ["/platforms", "platforms"],
    ["/platforms/", "platforms"],
    ["/platform/12", "platforms"],
    ["/collections", "collections"],
    ["/collection/smart/3", "collections"],
    ["/search", "search"],
  ])("puts %s under %s", (path, id) => {
    expect(navDestinationAt(path)).toBe(id);
  });

  it.each(["/platform-invalid", "/collectionsx", "/searching", "/rom/7"])(
    "leaves %s outside every destination",
    (path) => {
      expect(navDestinationAt(path)).toBeNull();
    },
  );
});
