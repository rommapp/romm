// Lighthouse audits on a slow desktop: real LAN network, 6x CPU slowdown.
//
// Run:  npx playwright test --project=lighthouse
// View: open e2e/.output/lighthouse/<page>.html in a browser.
import { chromium, type Cookie } from "@playwright/test";
import lighthouse from "lighthouse";
import type * as LH from "lighthouse/types/lh.js";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import type { RouteName } from "../../src/plugins/routeNames";
import { LIGHTHOUSE_DIR } from "../support/output";
import { E2E_SITEMAP, type E2eSitemapEntry } from "../support/sitemap";
import { expect, test } from "../support/test";

type Audit = LH.Audit.Result;

const isFailing = (audit: Audit) => audit.score !== null && audit.score < 1;

// CLS savings are unitless, so only the timing metrics add up to milliseconds.
function savingsMs({ metricSavings = {} }: Audit): number {
  return Object.entries(metricSavings)
    .filter(([metric]) => metric !== "CLS")
    .reduce((sum, [, ms]) => sum + (ms ?? 0), 0);
}

function savingsBytes({ details }: Audit): number {
  if (details?.type === "opportunity") return details.overallSavingsBytes ?? 0;
  if (details?.type === "table") return details.summary?.wastedBytes ?? 0;
  return 0;
}

/** The category's failing audits, biggest estimated win first, as message lines. */
function fixFirst(lhr: LH.Result, categoryId: string, count = 3): string {
  const lines = (lhr.categories[categoryId]?.auditRefs ?? [])
    .map(({ id }) => lhr.audits[id])
    .filter((audit): audit is Audit => audit !== undefined && isFailing(audit))
    .map((audit) => ({
      audit,
      ms: savingsMs(audit),
      bytes: savingsBytes(audit),
    }))
    .filter(({ ms, bytes }) => ms > 0 || bytes > 0)
    .sort((a, b) => b.ms - a.ms || b.bytes - a.bytes)
    .slice(0, count)
    .map(
      ({ audit }, i) =>
        `  ${i + 1}. ${audit.title}${audit.displayValue ? `: ${audit.displayValue}` : ""}`,
    );
  return lines.length > 0 ? `\nFix first:\n${lines.join("\n")}` : "";
}

// Every category that Lighthouse's default config ships. LH types categories
// as Record<string, Category>, so this union is the closest we can get to an
// exhaustive type for the keys that will actually appear in lhr.categories.
type LhCategoryId = "performance" | "accessibility" | "best-practices" | "seo";

// The subset we actually run and assert on. Drives both onlyCategories (so LH
// skips the rest) and the shape of AuditedCategories below.
const LIGHTHOUSE_CATEGORIES = [
  "performance",
  // we are going to skip a11y and best-practices so it goes faster.
  // "accessibility",
  // "best-practices",
] as const satisfies readonly LhCategoryId[];

// Thresholds may cover any LH category. Only the ones that were actually
// audited (present in LIGHTHOUSE_CATEGORIES) get a test. This lets you comment
// entries in/out of LIGHTHOUSE_CATEGORIES without changing the threshold objects.
type PageThresholds = Partial<Record<LhCategoryId, number>>;

// Desktop size, no network throttling (real LAN), 6x CPU penalty.
const auditConfig: LH.Config = {
  extends: "lighthouse:default",
  settings: {
    // this makes it go faster, so if you only want to run a11y or best-practices,
    // you can comment out performance in LIGHTHOUSE_CATEGORIES.
    onlyCategories: [...LIGHTHOUSE_CATEGORIES],
    formFactor: "desktop",
    throttlingMethod: "simulate",
    throttling: {
      rttMs: 0,
      throughputKbps: 0,
      requestLatencyMs: 0,
      downloadThroughputKbps: 0,
      uploadThroughputKbps: 0,
      // simulate 2x slower than a steam deck.
      cpuSlowdownMultiplier: 6,
    },
    screenEmulation: {
      mobile: false,
      width: 1350,
      height: 940,
      deviceScaleFactor: 1,
      disabled: false,
    },
  },
};

// Must match --remote-debugging-port. Single worker means no port conflicts.
const CDP_PORT = 9222;

type AuditPage = E2eSitemapEntry & { thresholds: PageThresholds };

// Tune thresholds after a baseline run against your actual site.
const DEFAULT_THRESHOLDS: PageThresholds = {
  // very, very low. :'(
  performance: 75,
  accessibility: 90,
  "best-practices": 90,
};

// Pages that hold a different bar than DEFAULT_THRESHOLDS.
const PAGE_THRESHOLDS: Partial<Record<RouteName, PageThresholds>> = {};

const AUDIT_PAGES: Record<string, AuditPage> = Object.fromEntries(
  E2E_SITEMAP.map((entry) => [
    entry.id,
    { ...entry, thresholds: PAGE_THRESHOLDS[entry.id] ?? DEFAULT_THRESHOLDS },
  ]),
);

// Runs Lighthouse and returns lhr. Writes HTML + JSON reports as a side-effect
// so the full report is available whatever the scores.
async function runAudit(
  pageUrl: string,
  pageName: string,
  storageState: E2eSitemapEntry["storageState"],
): Promise<LH.Result> {
  // Lighthouse opens its tab in the default context, and only a persistent
  // context is the default one, so the session cookie has to live here.
  const context = await chromium.launchPersistentContext("", {
    args: [`--remote-debugging-port=${CDP_PORT}`],
  });

  try {
    // Cookies only, without visiting the page, so the audit is a cold load.
    const { cookies }: { cookies: Cookie[] } =
      typeof storageState === "string"
        ? JSON.parse(readFileSync(storageState, "utf8"))
        : storageState;
    await context.addCookies(cookies);

    const runnerResult: LH.RunnerResult | undefined = await lighthouse(
      pageUrl,
      {
        port: CDP_PORT,
        disableStorageReset: true,
        skipAboutBlank: true,
        output: ["html", "json"],
      },
      auditConfig,
    );

    if (!runnerResult) throw new Error(`No Lighthouse result for ${pageName}`);

    const { lhr, report: reportFiles } = runnerResult;
    const landedOn = new URL(lhr.finalDisplayedUrl).pathname;
    if (landedOn !== new URL(pageUrl).pathname) {
      throw new Error(
        `Lighthouse for ${pageName} landed on ${lhr.finalDisplayedUrl}; is the session valid?`,
      );
    }
    const [htmlReport, jsonReport] = reportFiles as [string, string];

    mkdirSync(LIGHTHOUSE_DIR, { recursive: true });
    writeFileSync(`${LIGHTHOUSE_DIR}/${pageName}.html`, htmlReport);
    writeFileSync(`${LIGHTHOUSE_DIR}/${pageName}.json`, jsonReport);

    const summary = (
      Object.entries(lhr.categories) as [string, LH.Result.Category][]
    )
      .map(([id, c]) =>
        c.score !== null ? `${id}=${Math.round(c.score * 100)}` : `${id}=n/a`,
      )
      .join(" ");
    console.log(`[lighthouse:${pageName}] ${summary}`);

    return lhr;
  } finally {
    await context.close();
  }
}

// One test per page, so a failure never restarts a worker mid-page and
// re-runs that page's audit.
test.describe.configure({ mode: "default" });

for (const [
  pageName,
  { path, storageState, tag, thresholds },
] of Object.entries(AUDIT_PAGES)) {
  test.describe(pageName, { tag: [...tag] }, () => {
    let lhr: LH.Result;

    test.beforeAll(async ({}, testInfo) => {
      const { baseURL } = testInfo.project.use;
      lhr = await runAudit(new URL(path, baseURL).href, pageName, storageState);
    });

    test("lighthouse-report", async () => {
      await test.info().attach("lighthouse-report", {
        path: `${LIGHTHOUSE_DIR}/${pageName}.html`,
        contentType: "text/html",
      });

      // Soft, so every category under its threshold is reported.
      const audited = (Object.entries(thresholds) as [LhCategoryId, number][])
        .filter(([categoryId]) =>
          (LIGHTHOUSE_CATEGORIES as readonly LhCategoryId[]).includes(
            categoryId,
          ),
        )
        .map(([categoryId, threshold]) => ({
          categoryId,
          threshold,
          score: lhr.categories[categoryId]?.score ?? null,
        }));
      test.info().annotations.push(
        ...audited
          .filter(({ score }) => score === null)
          .map(({ categoryId }) => ({
            type: "lighthouse:n/a",
            description: `${categoryId}: Lighthouse could not score it`,
          })),
      );
      for (const { categoryId, threshold, score } of audited.filter(
        ({ score }) => score !== null,
      )) {
        const scoreAs100 = Math.round(score! * 100);
        expect
          .soft(
            scoreAs100,
            `${pageName} ${categoryId}: got ${scoreAs100}, need >= ${threshold}${fixFirst(lhr, categoryId)}`,
          )
          .toBeGreaterThanOrEqual(threshold);
      }
    });
  });
}
