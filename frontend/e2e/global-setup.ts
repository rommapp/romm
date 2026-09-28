import { readE2EEnv } from "./e2e-environment";
import { type Account, accountFor, type Role, ROLES } from "./fixtures/auth";

// Preflight, before any test or browser: the backend answers, each account
// signs in and can read ROMs, and the library has a game. One error lists every
// problem in about a second, instead of each test timing out on it later. The
// only place the suite calls the API directly: it isn't a test.

const TIMEOUT_MS = 5_000;

class PreflightError extends Error {
  constructor(problems: Record<string, string>) {
    const messages = Object.values(problems);
    super(
      [
        `The backend isn't ready for the e2e suite (${messages.length} problem(s)):`,
        ...messages.map((message) => `  - ${message}`),
      ].join("\n"),
    );
    this.name = "PreflightError";
    // The stack points into this file, which helps nobody fix their backend.
    this.stack = `${this.name}: ${this.message}`;
  }
}

/** Never throws: a network failure or timeout comes back as the Error. */
async function get(url: string, account?: Account): Promise<Response | Error> {
  const headers: HeadersInit = account
    ? {
        Authorization: `Basic ${Buffer.from(`${account.username}:${account.password}`).toString("base64")}`,
      }
    : {};
  try {
    return await fetch(url, {
      headers,
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    return error instanceof Error ? error : new Error(String(error));
  }
}

async function checkBackend(target: string): Promise<Record<string, string>> {
  const response = await get(`${target}/api/heartbeat`);
  if (response instanceof Error) {
    return {
      backend: `Nothing answered at ${target} (${response.message}). Start the backend, or fix E2E_DEV_PROXY_TARGET in e2e/.env.`,
    };
  }
  if (!response.ok) {
    return {
      backend: `GET /api/heartbeat returned ${response.status} at ${target}. Is E2E_DEV_PROXY_TARGET a RomM backend?`,
    };
  }
  return {};
}

async function checkAccount(
  target: string,
  role: Role,
  account: Account,
): Promise<Record<string, string>> {
  const response = await get(`${target}/api/roms?limit=1`, account);
  const who = `The ${role} account "${account.username}"`;
  if (response instanceof Error) {
    return {
      [role]: `${who} got no answer from GET /api/roms (${response.message}).`,
    };
  }
  if (response.status === 401) {
    return {
      [role]: `${who} can't sign in: check its password in e2e/.env, and that it exists on this backend.`,
    };
  }
  if (response.status === 403) {
    return { [role]: `${who} signs in but can't read ROMs.` };
  }
  if (!response.ok) {
    return { [role]: `GET /api/roms returned ${response.status} for ${who}.` };
  }
  return {};
}

async function checkLibrary(
  target: string,
  account: Account,
): Promise<Record<string, string>> {
  const response = await get(`${target}/api/roms?limit=1`, account);
  if (response instanceof Error || !response.ok) {
    return { library: "Couldn't count the library's games." };
  }
  const body: unknown = await response.json().catch(() => undefined);
  const total = (body as { total?: unknown } | undefined)?.total;
  if (typeof total !== "number") {
    return { library: "GET /api/roms didn't report a total." };
  }
  if (total === 0) {
    return {
      library:
        "The library has no games, and the specs open one. Scan a platform first.",
    };
  }
  return {};
}

export default async function globalSetup() {
  const env = readE2EEnv();
  const target = env.E2E_DEV_PROXY_TARGET;

  // Every other check would only repeat that the backend is unreachable.
  const backend = await checkBackend(target);
  if (Object.keys(backend).length) throw new PreflightError(backend);

  const accounts = await Promise.all(
    ROLES.map((role) => checkAccount(target, role, accountFor(env, role))),
  );
  const problems: Record<string, string> = Object.assign({}, ...accounts);
  // The admin sees every game, so its count is the library's.
  if (!problems.admin) {
    Object.assign(
      problems,
      await checkLibrary(target, accountFor(env, "admin")),
    );
  }
  if (Object.keys(problems).length) throw new PreflightError(problems);
}
