import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

// The only place the e2e suite reads its environment. A new variable goes in
// E2EEnv, EXPECTED, readE2EEnv(), .env.example, and e2e.yml if CI needs it.

const ENV_FILE = fileURLToPath(new URL("./.env", import.meta.url));
const ENV_FILE_LABEL = "frontend/e2e/.env";
const EXAMPLE_LABEL = "frontend/e2e/.env.example";
const PREFIX = "E2E_";

/** 1:1 with the environment variables. Required variables are required props. */
export interface E2EEnv {
  CI: boolean;
  E2E_ADMIN_USERNAME: string;
  E2E_ADMIN_PASSWORD: string;
  E2E_VIEWER_USERNAME: string;
  E2E_VIEWER_PASSWORD: string;
  E2E_DEV_PROXY_TARGET: string;
  E2E_WORKERS?: number;
}

type E2EKey = Exclude<keyof E2EEnv, "CI">;

/** What a valid value looks like, quoted in every error about that variable. */
const EXPECTED: Record<E2EKey, string> = {
  E2E_ADMIN_USERNAME: "required, the username of an admin account",
  E2E_ADMIN_PASSWORD: "required, that account's password",
  E2E_VIEWER_USERNAME:
    "required, the username of a non-admin account in the Viewer group",
  E2E_VIEWER_PASSWORD: "required, that account's password",
  E2E_DEV_PROXY_TARGET:
    "required, the RomM backend's http(s) URL, e.g. http://127.0.0.1:5000",
  E2E_WORKERS: "optional, a whole number of parallel workers (1 or more)",
};

/** Variables older versions of the suite read, and what replaces each. `shell`
 *  also flags one set in the process env, where it would otherwise be ignored;
 *  E2E_PASSWORD stays legal there because the seed script reads it. */
const REMOVED: Record<string, { action: string; shell: boolean }> = {
  E2E_BASE_URL: {
    action:
      "The suite now serves its own frontend. Set E2E_DEV_PROXY_TARGET to the backend's URL instead.",
    shell: true,
  },
  E2E_DEV_PORT: {
    action: "Set E2E_DEV_PROXY_TARGET=http://127.0.0.1:<port> instead.",
    shell: true,
  },
  E2E_PASSWORD: {
    action:
      "Set E2E_ADMIN_PASSWORD and E2E_VIEWER_PASSWORD. The seed script still reads E2E_PASSWORD from its own shell.",
    shell: false,
  },
};

/** Thrown once, listing every problem. Names variables, never their values. */
export class E2EEnvError extends Error {
  constructor(problems: string[], source: string) {
    super(
      [
        `The e2e environment has ${problems.length} problem(s), read from ${source}:`,
        ...problems.map((p) => `  - ${p}`),
        `${EXAMPLE_LABEL} lists every variable and its format.`,
      ].join("\n"),
    );
    this.name = "E2EEnvError";
    // The stack points into this parser, which helps nobody fix their env.
    this.stack = `${this.name}: ${this.message}`;
  }
}

type RawVars = Record<string, string | undefined>;

/** Syntax problems `parseEnv` would otherwise skip or silently resolve. */
function lintEnvFile(text: string): string[] {
  const problems: string[] = [];
  const seen = new Map<string, number>();
  text.split(/\r?\n/).forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) return;
    const key = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(
      trimmed,
    )?.[1];
    if (!key) {
      problems.push(`line ${index + 1} is not in KEY=value form`);
    } else if (seen.has(key)) {
      problems.push(
        `${key} is set more than once (lines ${seen.get(key)} and ${index + 1})`,
      );
    } else {
      seen.set(key, index + 1);
    }
  });
  return problems;
}

/** The variables to validate, plus any problems with where they came from. */
function readSource(ci: boolean): {
  label: string;
  vars: RawVars;
  problems: string[];
} {
  if (!existsSync(ENV_FILE)) {
    if (!ci) {
      throw new E2EEnvError(
        [
          `${ENV_FILE_LABEL} does not exist. Copy ${EXAMPLE_LABEL} to it and fill it in.`,
        ],
        ENV_FILE_LABEL,
      );
    }
    // CI has no file: the workflow env is the source.
    const vars = Object.fromEntries(
      Object.entries(process.env).filter(([key]) => key.startsWith(PREFIX)),
    );
    return { label: "the process environment", vars, problems: [] };
  }

  const text = readFileSync(ENV_FILE, "utf8");
  const vars = parseEnv(text);
  const problems = lintEnvFile(text);
  for (const key of Object.keys(vars)) {
    if (!key.startsWith(PREFIX)) {
      // Anything else would leak into the dev server Playwright spawns.
      problems.push(
        `${key} is not allowed here: only ${PREFIX}* variables are`,
      );
    }
  }
  return { label: ENV_FILE_LABEL, vars, problems };
}

/** Parse and validate every variable the suite uses, throwing one
 *  `E2EEnvError` that lists every problem found. */
export function readE2EEnv(): E2EEnv {
  const ci = !!process.env.CI;
  const { label, vars, problems } = readSource(ci);

  const fromShell = label !== ENV_FILE_LABEL;
  for (const key of Object.keys(vars)) {
    if (!key.startsWith(PREFIX) || key in EXPECTED) continue;
    const removed = REMOVED[key];
    if (removed && (removed.shell || !fromShell)) {
      problems.push(`${key} is no longer used. ${removed.action}`);
    } else if (!removed) {
      problems.push(`${key} is not a variable the suite reads (a typo?)`);
    }
  }
  if (!fromShell) {
    for (const [key, { action, shell }] of Object.entries(REMOVED)) {
      if (shell && process.env[key] !== undefined) {
        problems.push(
          `${key} is set in your shell and is no longer used. ${action}`,
        );
      }
    }
  }

  const fail = (key: E2EKey, issue: string) =>
    problems.push(`${key} ${issue}. Expected: ${EXPECTED[key]}.`);

  // Names and URLs must be exact: stray whitespace usually means a quoting slip.
  const text = (key: E2EKey, required: boolean): string | undefined => {
    const value = vars[key];
    if (!value) {
      if (required) fail(key, "is missing or empty");
      return undefined;
    }
    if (value !== value.trim()) fail(key, "has leading or trailing whitespace");
    return value;
  };
  // Passwords are taken exactly as written, spaces included.
  const secret = (key: E2EKey): string | undefined => {
    const value = vars[key];
    if (!value) fail(key, "is missing or empty");
    return value || undefined;
  };

  const adminUsername = text("E2E_ADMIN_USERNAME", true);
  const adminPassword = secret("E2E_ADMIN_PASSWORD");
  const viewerUsername = text("E2E_VIEWER_USERNAME", true);
  const viewerPassword = secret("E2E_VIEWER_PASSWORD");

  const proxyTarget = text("E2E_DEV_PROXY_TARGET", true);
  if (proxyTarget !== undefined) {
    const url = URL.parse(proxyTarget);
    if (!url || (url.protocol !== "http:" && url.protocol !== "https:")) {
      fail("E2E_DEV_PROXY_TARGET", "is not an http(s) URL");
    }
  }

  const workersRaw = text("E2E_WORKERS", false);
  const workers = workersRaw === undefined ? undefined : Number(workersRaw);
  if (workers !== undefined && !(Number.isInteger(workers) && workers >= 1)) {
    fail("E2E_WORKERS", "is not a whole number of 1 or more");
  }

  if (adminUsername && adminUsername === viewerUsername) {
    problems.push(
      "E2E_ADMIN_USERNAME and E2E_VIEWER_USERNAME are the same account. The permission tests compare the two, so they must differ.",
    );
  }

  if (problems.length) throw new E2EEnvError(problems, label);

  // Every required value was checked above, so the assertions below hold.
  return Object.freeze({
    CI: ci,
    E2E_ADMIN_USERNAME: adminUsername!,
    E2E_ADMIN_PASSWORD: adminPassword!,
    E2E_VIEWER_USERNAME: viewerUsername!,
    E2E_VIEWER_PASSWORD: viewerPassword!,
    E2E_DEV_PROXY_TARGET: proxyTarget!,
    E2E_WORKERS: workers,
  });
}

/** Env for the server Playwright starts. Vite lets process env beat .env files,
 *  so the backend comes from here, never from the project's .env. */
export function webServerEnv(env: E2EEnv): Record<string, string> {
  return { DEV_PROXY_TARGET: env.E2E_DEV_PROXY_TARGET };
}
