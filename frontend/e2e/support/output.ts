import { fileURLToPath } from "node:url";

// Everything the Playwright suite writes lives under e2e/.output/ (gitignored),
// so deleting that one folder resets every run.
const OUTPUT_DIR = fileURLToPath(new URL("../.output/", import.meta.url));

/** A Playwright suite, named after the e2e/ folder that holds its tests. */
export type Suite = "specs" | "lighthouse" | "axe";

/** Where a suite writes its per-test traces and screenshots, and its HTML report. */
export function suiteOutput(suite: Suite) {
  return {
    results: `${OUTPUT_DIR}${suite}/results`,
    report: `${OUTPUT_DIR}${suite}/report`,
  };
}

/** Saved sign-in sessions (live cookies). */
export const AUTH_DIR = `${OUTPUT_DIR}auth`;

/** HTML and JSON reports from the Lighthouse suite, one file per page. */
export const LIGHTHOUSE_DIR = `${OUTPUT_DIR}lighthouse`;

export const AXE_DIR = `${OUTPUT_DIR}axe`;
