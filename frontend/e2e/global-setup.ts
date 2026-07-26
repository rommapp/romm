import { chromium, type FullConfig } from "@playwright/test";
import {
  gotoFirstRom,
  gotoOwnProfile,
  login,
  seedUiState,
} from "./fixtures/auth";

// Warm the dev server before any test runs.
//
// Vite compiles on demand, and the specs' routes pull in big lazily-loaded
// chunks (GameDetails, and MediaTab's per-subtab async panels). On a cold server
// whichever test reaches a route first pays its compile cost out of its own
// timeout and flakes while the rest pass -- which reads like a real, targeted
// failure and isn't. Walking the routes once here spends that cost outside every
// test's budget.
//
// This deliberately drives the SAME helpers the specs use rather than
// reimplementing login/navigation: a private copy of those selectors silently
// drifts from the real ones (it already did once).
export default async function globalSetup(config: FullConfig) {
  // Escape hatch for debugging a single spec against an already-warm server.
  if (process.env.E2E_SKIP_WARMUP) return;

  const baseURL =
    config.projects[0]?.use?.baseURL ??
    process.env.E2E_BASE_URL ??
    "http://localhost:3000";

  const browser = await chromium.launch();
  try {
    // baseURL on the context is what lets the shared helpers' relative
    // `page.goto("/login")` work here.
    const page = await browser.newPage({ baseURL });
    page.setDefaultTimeout(120_000);
    await seedUiState(page, "dark");

    // Passive pass FIRST, with no interaction: loading the app is what makes
    // Vite discover and pre-bundle its dependencies, and it force-reloads the
    // page when it does ("optimized dependencies changed. reloading"). Absorbing
    // that here means the tests -- and the login below -- don't get reloaded out
    // from under themselves.
    await page.goto("/login", { waitUntil: "networkidle", timeout: 180_000 });
    await page.waitForSelector("form.r-v2-login-form", { timeout: 120_000 });

    await login(page, "admin", { timeout: 60_000 });

    // From here on the steps are best-effort: each one is only warming a chunk,
    // and a `.catch()` that inherits the 120s default above would sit there for
    // two minutes per miss (which is what made this setup take 8 minutes).
    page.setDefaultTimeout(15_000);
    const warm = (p: Promise<unknown>) => p.catch(() => {});

    // Compile the ROM details route and each of its tab panels.
    await warm(gotoFirstRom(page));
    for (const tab of ["Media", "Files"]) {
      await warm(page.getByRole("tab", { name: tab }).click());
    }
    for (const subtab of ["Manual", "Screenshots", "Artwork", "Soundtrack"]) {
      await warm(
        page.locator(".r-v2-media__subtab-btn", { hasText: subtab }).click(),
      );
    }
    await warm(page.waitForLoadState("networkidle"));

    // And the profile route.
    await warm(gotoOwnProfile(page));
  } finally {
    await browser.close();
  }
}
