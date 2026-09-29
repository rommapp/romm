// Attaches a screenshot per impact level with each offending element outlined
// in that level's colour. Self-contained: delete this file and its one call in
// axe.spec.ts to remove it.
import type { Page } from "@playwright/test";
import type { ImpactValue, NodeResult, Result as AxeViolation } from "axe-core";
import { test } from "../support/test";

type Impact = Exclude<ImpactValue, null>;

const IMPACT_COLORS: Record<Impact, string> = {
  critical: "#ff0033",
  serious: "#ff00ff",
  moderate: "#ffd400",
  minor: "#00b4ff",
};

// Outlines keep the element readable, where a mask would cover it. One rule
// per selector, so a selector the browser rejects drops only its own rule.
function highlightCss(selectors: readonly string[], color: string): string {
  return selectors
    .map(
      (selector) => `${selector} {
        outline: 5px solid ${color} !important;
        outline-offset: 3px !important;
        box-shadow: 0 0 0 3px #fff, 0 0 24px 10px ${color} !important;
      }`,
    )
    .join("\n");
}

// Only a plain selector in the top document; iframe and shadow DOM targets
// (arrays) are left to the JSON report.
function selectorOf({ target }: NodeResult): string[] {
  const [selector, ...inFrames] = target;
  return typeof selector === "string" && inFrames.length === 0
    ? [selector]
    : [];
}

export async function attachViolationScreenshots(
  page: Page,
  violations: readonly AxeViolation[],
): Promise<void> {
  const byImpact = (Object.keys(IMPACT_COLORS) as Impact[])
    .map((impact) => ({
      impact,
      selectors: violations
        .filter((v) => v.impact === impact)
        .flatMap((v) => v.nodes.flatMap(selectorOf)),
    }))
    .filter(({ selectors }) => selectors.length > 0);

  for (const { impact, selectors } of byImpact) {
    // A failed capture must never hide the violations themselves.
    try {
      const body = await page.screenshot({
        fullPage: true,
        style: highlightCss(selectors, IMPACT_COLORS[impact]),
      });
      await test
        .info()
        .attach(`axe-${impact}`, { body, contentType: "image/png" });
    } catch (error) {
      console.warn(`[axe] no ${impact} screenshot: ${String(error)}`);
    }
  }
}
