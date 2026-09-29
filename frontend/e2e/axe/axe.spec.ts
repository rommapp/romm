// axe-core a11y audits: critical and serious violations block the run.
//
// Run:  npx playwright test --project=axe
// View: open e2e/.output/axe/<page>.json, one violation record per entry.
import { AxeBuilder } from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import type { ImpactValue, Result as AxeViolation } from "axe-core";
import { mkdirSync, writeFileSync } from "node:fs";
import { gotoHydrated, SIGNED_OUT } from "../support/auth";
import { AXE_DIR } from "../support/output";
import {
  E2E_SITEMAP,
  type E2eSitemapEntry,
  type E2eSitemapId,
} from "../support/sitemap";
import { expect, test } from "../support/test";
import { attachViolationScreenshots } from "./highlight";

// All impact levels in severity order, for the always-on log line.
const ALL_IMPACTS: readonly ImpactValue[] = [
  "critical",
  "serious",
  "moderate",
  "minor",
];

// Per-page blocking impact configuration. A violation at a listed impact level
// fails the test; others are written to the report only. Typed against
// ImpactValue so a typo or a removed level is a compile error.
type PageBlockingImpacts = readonly ImpactValue[];

// Tune per page after a baseline run against your actual site.
const DEFAULT_BLOCKING_IMPACTS: PageBlockingImpacts = ["critical", "serious"];

type AxePage = E2eSitemapEntry & { blockingImpacts: PageBlockingImpacts };

// Pages that hold a different bar than DEFAULT_BLOCKING_IMPACTS.
const PAGE_BLOCKING_IMPACTS: Partial<
  Record<E2eSitemapId, PageBlockingImpacts>
> = {};

const AXE_PAGES: Record<string, AxePage> = Object.fromEntries(
  E2E_SITEMAP.map((entry) => [
    entry.id,
    {
      ...entry,
      blockingImpacts:
        PAGE_BLOCKING_IMPACTS[entry.id] ?? DEFAULT_BLOCKING_IMPACTS,
    },
  ]),
);

// Signed-out pages render the login form; gotoHydrated would reject them.
const isSignedOut = ([, { storageState }]: [string, AxePage]) =>
  storageState === SIGNED_OUT;
const SIGNED_OUT_PAGES = Object.entries(AXE_PAGES).filter(isSignedOut);
const SIGNED_IN_PAGES = Object.entries(AXE_PAGES).filter(
  (entry) => !isSignedOut(entry),
);

/** Runs axe, writes the full violation JSON, logs the impact summary, and
 *  returns the violations that exceed the page's blocking threshold. */
async function runAxe(
  page: Page,
  pageName: string,
  blockingImpacts: PageBlockingImpacts,
): Promise<{ blocking: AxeViolation[]; message: string }> {
  const { violations } = await new AxeBuilder({ page }).analyze();

  mkdirSync(AXE_DIR, { recursive: true });
  writeFileSync(
    `${AXE_DIR}/${pageName}.json`,
    JSON.stringify(violations, null, 2),
  );

  const impactSummary = ALL_IMPACTS.map((impact) => {
    const n = violations.filter((v) => v.impact === impact).length;
    return `${impact}=${n}`;
  }).join(" ");
  console.log(`[axe:${pageName}] ${impactSummary}`);

  const blockingSet = new Set<ImpactValue>(blockingImpacts);
  const blocking = violations.filter(
    (v): v is AxeViolation & { impact: ImpactValue } =>
      v.impact != null && blockingSet.has(v.impact),
  );
  await attachViolationScreenshots(page, blocking);

  const checkedImpacts = blockingImpacts.join(", ");
  const message = `${pageName}: ${blocking.length} violation(s) at [${checkedImpacts}]; see ${AXE_DIR}/${pageName}.json`;

  return { blocking, message };
}

for (const [
  pageName,
  { path, storageState, tag, blockingImpacts },
] of SIGNED_OUT_PAGES) {
  test.describe(pageName, { tag: [...tag] }, () => {
    test.use({ storageState });

    test(`no violations at [${blockingImpacts.join(", ")}]`, async ({
      page,
    }) => {
      await page.goto(path);
      await page.locator("form.r-v2-login-form").waitFor();

      const { blocking, message } = await runAxe(
        page,
        pageName,
        blockingImpacts,
      );
      expect(blocking, message).toHaveLength(0);
    });
  });
}

for (const [
  pageName,
  { path, storageState, tag, blockingImpacts },
] of SIGNED_IN_PAGES) {
  test.describe(pageName, { tag: [...tag] }, () => {
    test.use({ storageState });

    test(`no violations at [${blockingImpacts.join(", ")}]`, async ({
      page,
    }) => {
      await gotoHydrated(page, path);

      const { blocking, message } = await runAxe(
        page,
        pageName,
        blockingImpacts,
      );
      expect(blocking, message).toHaveLength(0);
    });
  });
}
