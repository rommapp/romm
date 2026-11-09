import { describe, expect, it, vi } from "vitest";
import { navDestinationAt, useNavDestinations } from "./index";

vi.mock("vue-i18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock("vue-router", () => ({ useRoute: () => ({ path: "/" }) }));

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

describe("useNavDestinations", () => {
  it("pairs each glyph with the one shown on the active tab", () => {
    const { destinations } = useNavDestinations();
    const icons = Object.fromEntries(
      destinations.value.map((d) => [d.id, [d.icon, d.activeIcon]]),
    );
    expect(icons).toEqual({
      home: ["mdi-home-outline", "mdi-home"],
      platforms: ["mdi-controller", "mdi-controller"],
      collections: ["mdi-bookmark-outline", "mdi-bookmark"],
      search: ["mdi-magnify", "mdi-magnify"],
    });
  });
});
