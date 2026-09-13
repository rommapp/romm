import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  DEFAULT_CACHE_LIMIT_BYTES,
  type DesktopConfig,
} from "../../shared/types.ts";
import {
  applyTokens,
  coreFileName,
  isSafeCoreName,
  resolveCore,
  resolveLaunch,
} from "./resolve.ts";

function baseConfig(patch: Partial<DesktopConfig> = {}): DesktopConfig {
  return {
    serverUrl: "https://romm.example.com",
    retroarchPath: null,
    retroarchCoresPath: null,
    emulators: [],
    cachePath: null,
    cacheLimitBytes: DEFAULT_CACHE_LIMIT_BYTES,
    trustedCertificates: [],
    ...patch,
  };
}

/** A throwaway tree standing in for a RetroArch install. */
function fakeInstall(cores: string[]) {
  const root = mkdtempSync(join(tmpdir(), "romm-retroarch-"));
  const binary = join(root, "retroarch");
  writeFileSync(binary, "");
  for (const core of cores) writeFileSync(join(root, coreFileName(core)), "");
  return { root, binary };
}

test("isSafeCoreName accepts real core names", () => {
  assert.ok(isSafeCoreName("mupen64plus_next"));
  assert.ok(isSafeCoreName("snes9x"));
});

test("isSafeCoreName rejects anything that could escape the cores directory", () => {
  for (const bad of [
    "../../bin/sh",
    "core/../..",
    "core.so",
    "core name",
    "Core",
    "",
  ]) {
    assert.equal(isSafeCoreName(bad), false, `${bad} must be rejected`);
  }
});

test("applyTokens substitutes without splitting argv entries", () => {
  const args = applyTokens(["-L", "{core}", "{rom}"], {
    rom: "/cache/My Game (USA).zip",
    core: "/cores/snes9x_libretro.so",
  });
  assert.deepEqual(args, [
    "-L",
    "/cores/snes9x_libretro.so",
    "/cache/My Game (USA).zip",
  ]);
});

test("resolveCore skips unsafe and missing cores", () => {
  const { root } = fakeInstall(["mgba"]);
  const core = resolveCore(root, ["../evil", "gambatte", "mgba"]);
  assert.equal(core?.name, "mgba");
});

test("resolveCore returns null when nothing is installed", () => {
  const { root } = fakeInstall([]);
  assert.equal(resolveCore(root, ["snes9x"]), null);
});

test("resolveLaunch builds a RetroArch command from the first installed core", () => {
  const { root, binary } = fakeInstall(["snes9x"]);
  const launch = resolveLaunch({
    config: baseConfig({ retroarchPath: binary, retroarchCoresPath: root }),
    platformSlug: "snes",
    cores: ["snes9x"],
    romPath: "/cache/1-game.sfc",
  });
  assert.equal(launch.command, binary);
  assert.deepEqual(launch.args, [
    "-L",
    join(root, coreFileName("snes9x")),
    "/cache/1-game.sfc",
  ]);
  assert.match(launch.label, /RetroArch/);
});

test("resolveLaunch prefers a per-platform mapping over RetroArch", () => {
  const { root, binary } = fakeInstall(["snes9x"]);
  const standalone = join(root, "dolphin");
  writeFileSync(standalone, "");
  const launch = resolveLaunch({
    config: baseConfig({
      retroarchPath: binary,
      retroarchCoresPath: root,
      emulators: [
        {
          platformSlug: "ngc",
          command: standalone,
          args: ["-e", "{rom}"],
          label: "Dolphin",
        },
      ],
    }),
    platformSlug: "ngc",
    cores: [],
    romPath: "/cache/2-game.iso",
  });
  assert.equal(launch.command, standalone);
  assert.deepEqual(launch.args, ["-e", "/cache/2-game.iso"]);
  assert.equal(launch.label, "Dolphin");
});

test("resolveLaunch falls back to a wildcard mapping", () => {
  const { root } = fakeInstall([]);
  const generic = join(root, "generic");
  writeFileSync(generic, "");
  const launch = resolveLaunch({
    config: baseConfig({
      emulators: [{ platformSlug: "*", command: generic, args: ["{rom}"] }],
    }),
    platformSlug: "anything",
    cores: [],
    romPath: "/cache/3-game.bin",
  });
  assert.equal(launch.command, generic);
});

test("resolveLaunch reports a platform with no known cores", () => {
  const { root, binary } = fakeInstall(["snes9x"]);
  assert.throws(
    () =>
      resolveLaunch({
        config: baseConfig({ retroarchPath: binary, retroarchCoresPath: root }),
        platformSlug: "switch",
        cores: [],
        romPath: "/cache/4-game.xci",
      }),
    { code: "unsupported-platform" },
  );
});

test("resolveLaunch reports cores that are known but not installed", () => {
  const { root, binary } = fakeInstall([]);
  assert.throws(
    () =>
      resolveLaunch({
        config: baseConfig({ retroarchPath: binary, retroarchCoresPath: root }),
        platformSlug: "n64",
        cores: ["mupen64plus_next"],
        romPath: "/cache/5-game.z64",
      }),
    { code: "no-emulator-configured" },
  );
});

test("resolveLaunch reports a configured emulator that has been removed", () => {
  assert.throws(
    () =>
      resolveLaunch({
        config: baseConfig({
          emulators: [
            { platformSlug: "psx", command: "/nope/duckstation", args: [] },
          ],
        }),
        platformSlug: "psx",
        cores: [],
        romPath: "/cache/6-game.chd",
      }),
    { code: "emulator-not-found" },
  );
});
