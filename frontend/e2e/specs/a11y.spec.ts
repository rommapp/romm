import type { RouteName } from "../../src/plugins/routeNames";
import { expectNoA11yViolations } from "../support/a11y";
import { STORAGE_STATE } from "../support/auth";
import { isAdminOnly, openPage, PAGES, type PageDef } from "../support/pages";
import { test } from "../support/test";

// Every page loads.spec.ts opens has no critical axe violations,
// checked once, as the viewer unless the page is admin-only.
for (const [name, def] of Object.entries(PAGES) as [RouteName, PageDef][]) {
  if ("skip" in def) continue;
  const { open } = def;
  const role = isAdminOnly(name) ? "admin" : "viewer";

  test.describe(name, { tag: `@page:${name}` }, () => {
    test.use({ storageState: STORAGE_STATE[role] });

    test("has no critical a11y violations", async ({ page }) => {
      await openPage(page, open);
      await expectNoA11yViolations(page);
    });
  });
}
