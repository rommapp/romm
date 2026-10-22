import { describe, expect, it } from "vitest";
import { ROUTES } from "@/plugins/routeNames";
import { v2RouteForConsole } from "./consoleRedirect";

describe("v2RouteForConsole", () => {
  it("boots the v2 player for a console play link", () => {
    expect(
      v2RouteForConsole({
        name: ROUTES.CONSOLE_PLAY,
        params: { rom: "3" },
        query: { snapshot: "30" },
      }),
    ).toEqual({
      name: ROUTES.EMULATORJS,
      params: { rom: "3" },
      query: { snapshot: "30" },
    });
  });

  it.each([
    [ROUTES.CONSOLE_HOME, {}, { name: ROUTES.HOME }],
    [
      ROUTES.CONSOLE_PLATFORM,
      { id: "4" },
      { name: ROUTES.PLATFORM, params: { platform: "4" } },
    ],
    [
      ROUTES.CONSOLE_SMART_COLLECTION,
      { id: "9" },
      { name: ROUTES.SMART_COLLECTION, params: { collection: "9" } },
    ],
    [
      ROUTES.CONSOLE_ROM,
      { rom: "3" },
      { name: ROUTES.ROM, params: { rom: "3" } },
    ],
  ])("sends %s to the matching v2 page", (name, params, expected) => {
    expect(v2RouteForConsole({ name, params, query: {} })).toEqual(expected);
  });

  it("leaves every other route alone", () => {
    expect(
      v2RouteForConsole({
        name: ROUTES.EMULATORJS,
        params: { rom: "3" },
        query: {},
      }),
    ).toBeNull();
  });
});
