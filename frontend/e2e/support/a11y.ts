import { AxeBuilder } from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./test";

// Lower impacts are attached to the report but don't fail the test. Add
// "serious" once the color-contrast and focus findings at that level are fixed.
const BLOCKING_IMPACTS = new Set(["critical"]);

/** Run axe on the page as it stands, attach every violation to the report,
 *  and fail on any at a blocking impact. */
export async function expectNoA11yViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  if (violations.length > 0) {
    await test.info().attach("axe-violations", {
      body: JSON.stringify(violations, null, 2),
      contentType: "application/json",
    });
  }

  const blocking = violations
    .filter(({ impact }) => impact && BLOCKING_IMPACTS.has(impact))
    .map((v) => `${v.impact}: ${v.id} on ${v.nodes.length} element(s)`);
  expect(
    blocking,
    "axe violations; the attached JSON lists each element",
  ).toEqual([]);
}
