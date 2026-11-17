#!/usr/bin/env node

/**
 * Server-side ROM patcher helper script.
 *
 * Uses RomPatcher.js (https://github.com/marcrobledo/RomPatcher.js/) to apply
 * a patch file to a ROM file, writing the result to an output path.
 *
 * Usage:
 *   node patcher.js <rom_path> <patch_path> <output_path> <max_output_bytes>
 *
 * Exit codes:
 *   0 - success
 *   1 - usage / argument error
 *   2 - patching error
 *   3 - the patch declares an output larger than max_output_bytes
 */

const path = require("path");
const fs = require("fs");

// Resolve the RomPatcher.js library directory. Two install layouts are supported:
//   1. Relocated next to this script (docker/Dockerfile copies it as a sibling).
//   2. Plain `npm install`, leaving it under the local node_modules.
function resolveRomPatcherBase() {
  const sibling = path.resolve(__dirname, "rom-patcher-js");
  if (fs.existsSync(sibling)) {
    return sibling;
  }
  return path.dirname(
    require.resolve("rom-patcher/rom-patcher-js/RomPatcher.js"),
  );
}

const ROM_PATCHER_BASE = resolveRomPatcherBase();

// Load the library (sets globals that RomPatcher.js expects)
const BaseBinFile = require(
  path.join(ROM_PATCHER_BASE, "modules", "BinFile.js"),
);
require(path.join(ROM_PATCHER_BASE, "modules", "HashCalculator.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.aps_gba.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.aps_n64.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.bdf.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.bps.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.ips.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.pmsr.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.ppf.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.rup.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.ups.js"));
require(path.join(ROM_PATCHER_BASE, "modules", "RomPatcher.format.vcdiff.js"));
const RomPatcher = require(path.join(ROM_PATCHER_BASE, "RomPatcher.js"));

const args = process.argv.slice(2);
const maxOutputBytes = Number(args[3]);
if (args.length !== 4 || !Number.isSafeInteger(maxOutputBytes)) {
  console.error(
    "Usage: node patcher.js <rom_path> <patch_path> <output_path> <max_output_bytes>",
  );
  process.exit(1);
}

const [romPath, patchPath, outputPath] = args;

class OutputTooLargeError extends Error {}

// Every format allocates its output with `new BinFile(size)` from a size read
// out of the patch, so a tiny patch can otherwise demand gigabytes.
globalThis.BinFile = new Proxy(BaseBinFile, {
  construct(target, ctorArgs, newTarget) {
    const [source] = ctorArgs;
    if (typeof source === "number" && source > maxOutputBytes) {
      throw new OutputTooLargeError(
        `The patch declares an output of ${source} bytes (max ${maxOutputBytes})`,
      );
    }
    return Reflect.construct(target, ctorArgs, newTarget);
  },
});

try {
  // Validate input files exist
  if (!fs.existsSync(romPath)) {
    throw new Error(`ROM file not found: ${romPath}`);
  }
  if (!fs.existsSync(patchPath)) {
    throw new Error(`Patch file not found: ${patchPath}`);
  }

  // Load files using BinFile (Node.js mode accepts file paths)
  const romFile = new BinFile(romPath);
  const patchFile = new BinFile(patchPath);

  // Parse the patch format
  const patch = RomPatcher.parsePatchFile(patchFile);
  if (!patch) {
    throw new Error("Unsupported or invalid patch format");
  }

  // Check the patch's embedded source checksum (when present) against the ROM.
  // We still apply on mismatch, but report it so callers can warn the user.
  const validated = RomPatcher.validateRom(romFile, patch);

  // Apply patch (don't block on validation; the result is reported above)
  const patchedRom = RomPatcher.applyPatch(romFile, patch, {
    requireValidation: false,
    fixChecksum: false,
    outputSuffix: false,
  });

  // Extract binary data and write to output
  const data = patchedRom._u8array || patchedRom.u8array || patchedRom.data;
  if (!data) {
    throw new Error("Failed to extract patched ROM data");
  }

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(
    outputPath,
    Buffer.from(data.buffer, data.byteOffset, data.byteLength),
  );
  console.log(
    JSON.stringify({
      success: true,
      output: outputPath,
      size: data.byteLength,
      validated: validated,
    }),
  );
  process.exit(0);
} catch (err) {
  console.error(
    JSON.stringify({ success: false, error: err.message || String(err) }),
  );
  process.exit(err instanceof OutputTooLargeError ? 3 : 2);
}
