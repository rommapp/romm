import assert from "node:assert/strict";
import { join } from "node:path";
import { test } from "node:test";
import { resolveDownloadUrl, safeCacheFileName } from "./safety.ts";

const SERVER = "https://romm.example.com";

test("resolveDownloadUrl accepts an API path on the bound origin", () => {
  const url = resolveDownloadUrl(SERVER, "/api/roms/7/content/game.zip");
  assert.equal(url.href, `${SERVER}/api/roms/7/content/game.zip`);
});

test("resolveDownloadUrl preserves query parameters", () => {
  const url = resolveDownloadUrl(
    SERVER,
    "/api/roms/7/content/g.zip?file_ids=1,2",
  );
  assert.equal(url.searchParams.get("file_ids"), "1,2");
});

test("resolveDownloadUrl encodes the unescaped names getDownloadPath emits", () => {
  const url = resolveDownloadUrl(
    SERVER,
    "/api/roms/42/content/Chrono Trigger (USA).sfc",
  );
  assert.equal(
    url.href,
    `${SERVER}/api/roms/42/content/Chrono%20Trigger%20(USA).sfc`,
  );
});

test("resolveDownloadUrl rejects protocol-relative hosts", () => {
  assert.throws(() => resolveDownloadUrl(SERVER, "//evil.example/api/x"), {
    code: "invalid-request",
  });
});

test("resolveDownloadUrl rejects absolute off-origin URLs", () => {
  assert.throws(
    () => resolveDownloadUrl(SERVER, "https://evil.example/api/roms/1"),
    { code: "invalid-request" },
  );
});

test("resolveDownloadUrl rejects traversal that escapes the API root", () => {
  assert.throws(() => resolveDownloadUrl(SERVER, "/api/../../etc/passwd"), {
    code: "invalid-request",
  });
});

test("resolveDownloadUrl rejects non-API routes", () => {
  assert.throws(() => resolveDownloadUrl(SERVER, "/login"), {
    code: "invalid-request",
  });
});

test("safeCacheFileName collapses separators into one component", () => {
  assert.equal(safeCacheFileName("a/b\\c.zip", 1), "1-a_b_c.zip");
});

test("safeCacheFileName defuses traversal sequences", () => {
  const name = safeCacheFileName("../../etc/passwd", 3);
  assert.ok(name.startsWith("3-"));
  assert.ok(!name.includes("/"), "no path separator survives");
  assert.ok(!name.includes("\\"), "no windows separator survives");
  assert.equal(join("/cache", name), `/cache/${name}`);
});

test("safeCacheFileName always yields a non-empty name", () => {
  assert.equal(safeCacheFileName("", 9), "9-rom");
  assert.equal(safeCacheFileName("...", 9), "9-rom");
});
