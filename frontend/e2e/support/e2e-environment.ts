import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

// The only place the e2e suite reads its environment. A new variable goes in
// E2EEnv, DEFAULTS (if it has one), readE2EEnv(), .env.example, and e2e.yml if
// CI needs it.

const ENV_FILE = fileURLToPath(new URL("../.env", import.meta.url));
const EXAMPLE_LABEL = "frontend/e2e/.env.example";

export interface E2EEnv {
  CI: boolean;
  E2E_ADMIN_USERNAME: string;
  E2E_ADMIN_PASSWORD: string;
  E2E_VIEWER_USERNAME: string;
  E2E_VIEWER_PASSWORD: string;
  E2E_BASE_URL: string;
  E2E_WORKERS?: number;
  /** E2E_BASE_URL was not set, so the config serves the app with `npm run dev`. */
  startDevServer: boolean;
}

// The accounts .github/scripts/seed_e2e_users.py creates, and `npm run dev`.
const DEFAULTS = {
  E2E_ADMIN_USERNAME: "e2e_admin",
  E2E_ADMIN_PASSWORD: "e2e-Passw0rd!",
  E2E_VIEWER_USERNAME: "e2e_viewer",
  E2E_VIEWER_PASSWORD: "e2e-Passw0rd!",
  E2E_BASE_URL: "http://localhost:3000",
};

/** Thrown once, listing every problem. Names variables, never their values. */
export class E2EEnvError extends Error {
  constructor(problems: string[]) {
    super(
      [
        `The e2e environment has ${problems.length} problem(s):`,
        ...problems.map((p) => `  - ${p}`),
        `${EXAMPLE_LABEL} lists every variable and its format.`,
      ].join("\n"),
    );
    this.name = "E2EEnvError";
    // The stack points into this parser, which helps nobody fix their env.
    this.stack = `${this.name}: ${this.message}`;
  }
}

/** Parse and validate every variable the suite uses. Each one comes from the
 *  shell, then e2e/.env, then DEFAULTS. */
export function readE2EEnv(): E2EEnv {
  const file = existsSync(ENV_FILE)
    ? parseEnv(readFileSync(ENV_FILE, "utf8"))
    : {};
  const raw = (key: string) => process.env[key] || file[key] || undefined;
  const problems: string[] = [];

  const baseUrlRaw = raw("E2E_BASE_URL");
  let baseUrl = DEFAULTS.E2E_BASE_URL;
  if (baseUrlRaw !== undefined) {
    const url = URL.parse(baseUrlRaw.trim());
    if (!url || (url.protocol !== "http:" && url.protocol !== "https:")) {
      problems.push("E2E_BASE_URL is not an http(s) URL.");
    } else if (url.pathname !== "/" || url.search || url.hash) {
      problems.push("E2E_BASE_URL has a path, query or hash.");
    } else {
      baseUrl = url.origin;
    }
  }

  const workersRaw = raw("E2E_WORKERS");
  const workers = workersRaw === undefined ? undefined : Number(workersRaw);
  if (workers !== undefined && !(Number.isInteger(workers) && workers >= 1)) {
    problems.push("E2E_WORKERS is not a whole number of 1 or more.");
  }

  // Passwords are taken exactly as written, spaces included.
  const adminUsername =
    raw("E2E_ADMIN_USERNAME")?.trim() ?? DEFAULTS.E2E_ADMIN_USERNAME;
  const viewerUsername =
    raw("E2E_VIEWER_USERNAME")?.trim() ?? DEFAULTS.E2E_VIEWER_USERNAME;
  if (adminUsername === viewerUsername) {
    problems.push(
      "E2E_ADMIN_USERNAME and E2E_VIEWER_USERNAME are the same account. The permission tests compare the two, so they must differ.",
    );
  }

  if (problems.length) throw new E2EEnvError(problems);

  return Object.freeze({
    CI: !!process.env.CI,
    E2E_ADMIN_USERNAME: adminUsername,
    E2E_ADMIN_PASSWORD:
      raw("E2E_ADMIN_PASSWORD") ?? DEFAULTS.E2E_ADMIN_PASSWORD,
    E2E_VIEWER_USERNAME: viewerUsername,
    E2E_VIEWER_PASSWORD:
      raw("E2E_VIEWER_PASSWORD") ?? DEFAULTS.E2E_VIEWER_PASSWORD,
    E2E_BASE_URL: baseUrl,
    E2E_WORKERS: workers,
    startDevServer: baseUrlRaw === undefined,
  });
}
