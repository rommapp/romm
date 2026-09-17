import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import {
  isolatedPlayerUrls,
  playerIsolationHeaders,
} from "../scripts/playerIsolationHeaders";

// Vitest roots at frontend/, so the template sits one level above it.
const TEMPLATE = resolve(
  process.cwd(),
  "../docker/nginx/templates/default.conf.template",
);

type Middleware = (
  req: { url?: string },
  res: { setHeader: (name: string, value: string) => void },
  next: () => void,
) => void;

type ServerHook = "configureServer" | "configurePreviewServer";

/** Drive one of the plugin's server hooks and hand back its middleware. */
function middleware(hook: ServerHook = "configureServer"): Middleware {
  let registered: Middleware | undefined;
  const plugin = playerIsolationHeaders(TEMPLATE) as unknown as Record<
    ServerHook,
    (server: { middlewares: { use: (fn: Middleware) => void } }) => void
  >;
  plugin[hook]({
    middlewares: {
      use: (fn) => {
        registered = fn;
      },
    },
  });
  if (!registered) throw new Error("no middleware registered");
  return registered;
}

function headersFor(
  url: string | undefined,
  hook?: ServerHook,
): Record<string, string> {
  const headers: Record<string, string> = {};
  const next = vi.fn();
  middleware(hook)(
    { url },
    {
      setHeader: (name, value) => {
        headers[name] = value;
      },
    },
    next,
  );
  expect(next).toHaveBeenCalledOnce();
  return headers;
}

const ISOLATED = {
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Cross-Origin-Opener-Policy": "same-origin",
};

/** A template holding `body` where the real one holds its maps. */
function templateWith(body: string): string {
  const dir = mkdtempSync(join(tmpdir(), "romm-nginx-"));
  const path = join(dir, "default.conf.template");
  writeFileSync(path, body, "utf8");
  return path;
}

describe("isolatedPlayerUrls", () => {
  it("reads the patterns the shipped template isolates", () => {
    const patterns = isolatedPlayerUrls(TEMPLATE);

    expect(patterns.some((p) => p.test("/rom/1/ejs"))).toBe(true);
    expect(patterns.some((p) => p.test("/console/rom/1/play"))).toBe(true);
  });

  // The template is the only list, so a rename that silently isolates nothing
  // would leave the dev server serving no headers at all.
  it("refuses a template with no map entries", () => {
    const path = templateWith(
      'map $request_uri $coep_header {\n  default "";\n}\n',
    );

    expect(() => isolatedPlayerUrls(path)).toThrow(/No COOP\/COEP map entries/);
  });

  it("refuses a template that is not there", () => {
    expect(() =>
      isolatedPlayerUrls("/nowhere/default.conf.template"),
    ).toThrow();
  });
});

describe("playerIsolationHeaders", () => {
  it.each([
    "/rom/1/ejs",
    "/rom/1/jsdos",
    // The v2 players carry their state in the query, and nginx matches the
    // request URI, so the query string has to be allowed for explicitly.
    "/rom/1/ejs?core=snes9x",
    "/console/rom/1/play",
  ])("isolates %s", (url) => {
    expect(headersFor(url)).toEqual(ISOLATED);
  });

  it.each([
    "/rom/1",
    "/rom/1/pico8",
    "/rom/1/ruffle",
    "/rom/1/stream",
    "/platform/2",
    "/api/roms/1/content/game.zip",
    "/assets/emulatorjs/data/loader.js",
  ])("leaves %s embeddable", (url) => {
    expect(headersFor(url)).toEqual({});
  });

  it("passes a request with no URL through", () => {
    expect(headersFor(undefined)).toEqual({});
  });

  // `vite preview` has no nginx in front of it either.
  it("isolates a player document on the preview server too", () => {
    expect(headersFor("/rom/1/ejs", "configurePreviewServer")).toEqual(
      ISOLATED,
    );
  });
});

// The plugin config is what vite.config.js passes it, and a moved template
// would otherwise only surface as a dev server serving no headers.
describe("the template vite.config.js points at", () => {
  it("is the one the tests read", () => {
    expect(readFileSync("vite.config.js", "utf8")).toContain(
      "../docker/nginx/templates/default.conf.template",
    );
  });
});
