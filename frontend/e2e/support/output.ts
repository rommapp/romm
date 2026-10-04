import { fileURLToPath } from "node:url";

// Everything the Playwright suite writes lives under e2e/.output/ (gitignored),
// so deleting that one folder resets every run.
const OUTPUT_DIR = fileURLToPath(new URL("../.output/", import.meta.url));

/** Per-test traces and screenshots. */
export const RESULTS_DIR = `${OUTPUT_DIR}specs/results`;

/** The HTML report: `npm run test:e2e:report`. */
export const REPORT_DIR = `${OUTPUT_DIR}specs/report`;

/** Saved sign-in sessions (live cookies). */
export const AUTH_DIR = `${OUTPUT_DIR}auth`;

/** The library facts library.setup.ts resolves for the specs. */
export const LIBRARY_FILE = `${OUTPUT_DIR}library.json`;
