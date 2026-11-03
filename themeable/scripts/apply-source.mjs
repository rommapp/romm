#!/usr/bin/env node
// Applies overlay/ and patches/ to a copy of RomM's source tree; the repository's own
// upstream files stay pristine, so --root must not be the checkout itself.
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { applyOverlay, applyPatches } from "../lib/source.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const mod = resolve(here, "..");
const args = parseArgs();
if (!args.root) fail("pass --root <source copy>");
const root = resolve(args.root);
if (root === resolve(mod, "..") && !args.force) fail("--root is the repository checkout; apply to a copy (or pass --force)");
const only = typeof args.only === "string" ? args.only : undefined;

try {
  const copied = applyOverlay(join(mod, "overlay"), root, { only, skipTests: !!args["no-tests"] });
  const applied = await applyPatches(join(mod, "patches"), root, { only });
  console.log(`themeable: overlay added ${copied.length} file(s); applied patches: ${applied.join(", ") || "none"}`);
} catch (e) {
  fail(e.message);
}
