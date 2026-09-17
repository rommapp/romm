import { describe, expect, it, vi } from "vitest";
import {
  isIsolatedPlayerUrl,
  playerIsolationHeaders,
} from "../scripts/playerIsolationHeaders";

type Middleware = (
  req: { url?: string },
  res: { setHeader: (name: string, value: string) => void },
  next: () => void,
) => void;

/** Drive the plugin's server hook and hand back the middleware it registered. */
function middleware(): Middleware {
  let registered: Middleware | undefined;
  const { configureServer } = playerIsolationHeaders() as unknown as {
    configureServer: (server: {
      middlewares: { use: (fn: Middleware) => void };
    }) => void;
  };
  configureServer({
    middlewares: {
      use: (fn) => {
        registered = fn;
      },
    },
  });
  if (!registered) throw new Error("no middleware registered");
  return registered;
}

function headersFor(url: string | undefined): Record<string, string> {
  const headers: Record<string, string> = {};
  const next = vi.fn();
  middleware()(
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

describe("isIsolatedPlayerUrl", () => {
  it.each([
    "/rom/1/ejs",
    "/rom/1/jsdos",
    // The v2 players carry their state in the query, and nginx matches the
    // request URI, so the query string has to be allowed for explicitly.
    "/rom/1/ejs?core=snes9x",
    "/console/rom/1/play",
  ])("isolates %s", (url) => {
    expect(isIsolatedPlayerUrl(url)).toBe(true);
  });

  it.each([
    "/rom/1",
    "/rom/1/pico8",
    "/rom/1/ruffle",
    "/rom/1/stream",
    "/platform/2",
    "/api/roms/1/content/game.zip",
    "/assets/emulatorjs/data/loader.js",
  ])("leaves %s alone", (url) => {
    expect(isIsolatedPlayerUrl(url)).toBe(false);
  });
});

describe("playerIsolationHeaders", () => {
  it("isolates a player document", () => {
    expect(headersFor("/rom/1/ejs")).toEqual(ISOLATED);
  });

  it("leaves every other document embeddable", () => {
    expect(headersFor("/rom/1")).toEqual({});
  });

  it("passes a request with no URL through", () => {
    expect(headersFor(undefined)).toEqual({});
  });
});
