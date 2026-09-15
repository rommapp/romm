import { describe, expect, it } from "vitest";
import router, { ROUTES } from "@/plugins/router";
import { notFoundComponent, v2RouteComponents } from "./routes";

function leafRouteFor(path: string) {
  const matched = router.resolve(path).matched;
  return matched[matched.length - 1];
}

describe("v2 route resolution", () => {
  it("renders the 404 view for an unmatched URL", () => {
    const leaf = leafRouteFor("/settings/administration");

    expect(leaf.name).toBe(ROUTES.NOT_FOUND);
    expect(leaf.components?.v2).toBe(notFoundComponent);
  });

  it("still renders the registered component for a matched URL", () => {
    const leaf = leafRouteFor("/administration");

    expect(leaf.name).toBe(ROUTES.ADMINISTRATION);
    expect(leaf.components?.v2).toBe(v2RouteComponents[ROUTES.ADMINISTRATION]);
  });
});
