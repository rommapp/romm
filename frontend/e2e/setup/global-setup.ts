import { type Account, accountFor, ROLES } from "../support/auth";
import { readE2EEnv } from "../support/e2e-environment";

// Preflight before any browser starts: the backend answers, both accounts sign
// in, and the library has a game. It lists every problem at once, instead of
// each test timing out on one. The only place the suite calls the API.

/** A response, or the network error as a value. */
function get(url: string, account?: Account): Promise<Response | Error> {
  const headers: HeadersInit = account
    ? {
        Authorization: `Basic ${btoa(`${account.username}:${account.password}`)}`,
      }
    : {};
  return fetch(url, { headers, signal: AbortSignal.timeout(5_000) }).catch(
    (error: Error) => error,
  );
}

function fail(problems: string[]): never {
  const error = new Error(
    [
      "The backend isn't ready for the e2e suite:",
      ...problems.map((problem) => `  - ${problem}`),
    ].join("\n"),
  );
  // The stack points into this file, which helps nobody fix their backend.
  error.stack = error.message;
  throw error;
}

export default async function globalSetup() {
  const env = readE2EEnv();
  const site = env.E2E_BASE_URL;

  const heartbeat = await get(`${site}/api/heartbeat`);
  if (heartbeat instanceof Error || !heartbeat.ok) {
    const why =
      heartbeat instanceof Error ? heartbeat.message : heartbeat.status;
    fail([`GET ${site}/api/heartbeat failed (${why}). Is the backend up?`]);
  }
  // The specs follow this checkout's UI, so an older backend can lack routes.
  const { SYSTEM } = (await heartbeat.json().catch(() => ({}))) as {
    SYSTEM?: { VERSION?: string; GIT_BRANCH?: string };
  };
  console.log(
    `e2e: testing ${site} (RomM ${SYSTEM?.VERSION ?? "unknown version"}, branch ${SYSTEM?.GIT_BRANCH ?? "unknown"})`,
  );

  const problems: string[] = [];
  for (const role of ROLES) {
    const account = accountFor(env, role);
    const response = await get(`${site}/api/roms?limit=1`, account);
    if (response instanceof Error || !response.ok) {
      const why =
        response instanceof Error
          ? response.message
          : response.status === 401
            ? "wrong username or password, or no such account"
            : response.status;
      problems.push(
        `The ${role} account "${account.username}" can't list ROMs (${why}).`,
      );
    } else if (role === "admin") {
      // The admin sees every game, so its count is the library's.
      const { total } = (await response.json()) as { total: number };
      if (total === 0) {
        problems.push("The library has no games. Scan a platform first.");
      }
    }
  }
  if (problems.length) fail(problems);
}
