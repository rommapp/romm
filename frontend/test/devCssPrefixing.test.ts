import path from "node:path";
import { createServer, type ViteDevServer } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

// The dev server is the only place this is observable: CI's e2e run serves a
// production build, and vitest.config.ts never loads vite.config.js, so a
// dropped `css.transformer` would leave every other check green.
describe("dev server CSS", () => {
  let server: ViteDevServer;

  beforeAll(async () => {
    server = await createServer({
      configFile: path.resolve(process.cwd(), "vite.config.js"),
      server: { middlewareMode: true },
      logLevel: "error",
    });
  }, 60_000);

  afterAll(async () => {
    await server?.close();
  });

  it("generates vendor prefixes, not only on the build's minify path", async () => {
    const result = await server.transformRequest(
      "/test/fixtures/prefix-probe.css",
    );
    expect(result?.code).toMatch(/-webkit-backdrop-filter:\s*blur\(1px\)/);
    expect(result?.code).toMatch(/[^-]backdrop-filter:\s*blur\(1px\)/);
  });
});
