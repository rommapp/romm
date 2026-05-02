#!/usr/bin/env node

/**
 * Server-side ROM patcher helper script.
 *
 * Uses RomPatcher.js (https://github.com/marcrobledo/RomPatcher.js/) to apply
 * a patch file to a ROM file, writing the result to an output path.
 *
 * Usage:
 *   node patcher.js <rom_path> <patch_path> <output_path>
 *
 * Exit codes:
 *   0 - success
 *   1 - usage / argument error
 *   2 - patching error
 */

const path = require("path");
const fs = require("fs");

// Resolve RomPatcher.js from the sibling node_modules (installed via package.json here).
const ROM_PATCHER_BASE = path.resolve(__dirname, "rom-patcher-js");

// Load the library (sets globals that RomPatcher.js expects)
require(path.join(ROM_PATCHER_BASE, "modules", "BinFile.js"));
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
if (args.length !== 3) {
  console.error("Usage: node patcher.js <rom_path> <patch_path> <output_path>");
  process.exit(1);
}

const [romPath, patchPath, outputPath] = args;

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

  // Apply patch
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
    }),
  );
  process.exit(0);
} catch (err) {
  console.error(
    JSON.stringify({ success: false, error: err.message || String(err) }),
  );
  process.exit(2);
}
