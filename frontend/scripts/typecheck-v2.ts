/**
 * typecheck-v2: runs vue-tsc with tsconfig.v2.json's stricter template checks
 * and fails only on diagnostics under src/v2/.
 *
 * The router imports every frozen v1 view, so v1 files are always in the
 * program, and vue-tsc can't scope its options by path. Run it via
 * `npm run typecheck:v2` (also part of `npm run typecheck`).
 */
import { spawnSync } from "node:child_process";

const result = spawnSync(
  "vue-tsc",
  ["--noEmit", "--pretty", "false", "-p", "tsconfig.v2.json"],
  { encoding: "utf8" },
);

if (result.error) throw result.error;

// A diagnostic is a `file(line,col): error TSxxxx: ...` line followed by
// indented continuation lines.
const diagnostics: string[][] = [];
for (const line of `${result.stdout}${result.stderr}`.split("\n")) {
  if (!line.trim()) continue;
  if (/^\s/.test(line) && diagnostics.length > 0) {
    diagnostics[diagnostics.length - 1].push(line);
  } else {
    diagnostics.push([line]);
  }
}

// Keep v2 files, and anything not tied to a file (config errors and the like).
const kept = diagnostics.filter(
  ([head]) => head.startsWith("src/v2/") || !/^\S+\(\d+,\d+\): /.test(head),
);

for (const diagnostic of kept) console.error(diagnostic.join("\n"));

if (kept.length > 0) process.exit(1);
if (result.status !== 0 && diagnostics.length === 0)
  process.exit(result.status ?? 1);
