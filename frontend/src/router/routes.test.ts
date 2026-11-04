import { describe, expect, it } from "vitest";
import router, { ROUTES } from "@/plugins/router";
import { notFoundComponent, routeComponents } from "./routes";

function leafRouteFor(path: string) {
  const matched = router.resolve(path).matched;
  return matched[matched.length - 1]!;
}

describe("v2 route resolution", () => {
  it("renders the 404 view for an unmatched URL", () => {
    const leaf = leafRouteFor("/settings/administration");

    expect(leaf.name).toBe(ROUTES.NOT_FOUND);
    expect(leaf.components?.default).toBe(notFoundComponent);
  });

  it("still renders the registered component for a matched URL", () => {
    const leaf = leafRouteFor("/administration");

    expect(leaf.name).toBe(ROUTES.ADMINISTRATION);
    expect(leaf.components?.default).toBe(
      routeComponents[ROUTES.ADMINISTRATION],
    );
  });

  it("renders the v2 pair shell for /pair", () => {
    const leaf = leafRouteFor("/pair?code=ABC123");

    expect(leaf.name).toBe(ROUTES.PAIR);
    expect(routeComponents[ROUTES.PAIR]).toBeDefined();
    expect(leaf.components?.default).toBe(routeComponents[ROUTES.PAIR]);
  });
});
