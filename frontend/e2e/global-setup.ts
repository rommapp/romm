import { readE2EEnv } from "./e2e-environment";
import { accountFor, ROLES } from "./fixtures/auth";

// Preflight, before any test or browser: the backend answers, each account
// signs in and can read ROMs, and the library has a game. One error lists every
// problem in about a second, instead of each test timing out on it later. The
// only place the suite calls the API directly: it isn't a test.

const TIMEOUT_MS = 5_000;

class PreflightError extends Error {
  constructor(problems: string[]) {
    super(
      [
        `The backend isn't ready for the e2e suite (${problems.length} problem(s)):`,
        ...problems.map((p) => `  - ${p}`),
      ].join("\n"),
    );
    this.name = "PreflightError";
    // The stack points into this file, which helps nobody fix their backend.
    this.stack = `${this.name}: ${this.message}`;
  }
}

async function get(url: string, authorization?: string): Promise<Response> {
  return fetch(url, {
    headers: authorization ? { Authorization: authorization } : {},
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
}

export default async function globalSetup() {
  const env = readE2EEnv();
  const target = env.E2E_DEV_PROXY_TARGET;

  try {
    const heartbeat = await get(`${target}/api/heartbeat`);
    if (!heartbeat.ok) {
      throw new PreflightError([
        `GET /api/heartbeat returned ${heartbeat.status} at ${target}. Is E2E_DEV_PROXY_TARGET a RomM backend?`,
      ]);
    }
  } catch (error) {
    if (error instanceof PreflightError) throw error;
    throw new PreflightError([
      `Nothing answered at ${target} (${(error as Error).message}). Start the backend, or fix E2E_DEV_PROXY_TARGET in e2e/.env.`,
    ]);
  }

  const problems: string[] = [];
  let libraryHasGames = false;
  for (const role of ROLES) {
    const { username, password } = accountFor(env, role);
    const basic = `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
    const response = await get(`${target}/api/roms?limit=1`, basic);
    if (response.status === 401) {
      problems.push(
        `The ${role} account "${username}" can't sign in: check its password in e2e/.env, and that it exists on this backend.`,
      );
    } else if (response.status === 403) {
      problems.push(
        `The ${role} account "${username}" signs in but can't read ROMs.`,
      );
    } else if (!response.ok) {
      problems.push(
        `GET /api/roms returned ${response.status} for the ${role} account "${username}".`,
      );
    } else {
      const body = (await response.json()) as { total?: number };
      libraryHasGames ||= (body.total ?? 0) > 0;
    }
  }
  if (!problems.length && !libraryHasGames) {
    problems.push(
      "The library has no games, and the specs open one. Scan a platform first.",
    );
  }
  if (problems.length) throw new PreflightError(problems);
}
