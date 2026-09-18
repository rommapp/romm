// Typechecks src/v2 with `strictTemplates`, which the v1 tree cannot pass.
//
// v2 reaches into v1 for the EmulatorJS player and the pairing view, so
// vue-tsc necessarily pulls the v1 component graph into the program. Only
// diagnostics pointing at src/v2 are reported; the rest go once v1 does.
import { spawnSync } from "node:child_process";

const V2_PATH = /^src\/v2\//;

const result = spawnSync(
  "vue-tsc",
  ["--noEmit", "-p", "tsconfig.v2.json", "--pretty", "false"],
  { encoding: "utf8", shell: true },
);

if (result.error) throw result.error;

const lines = `${result.stdout ?? ""}${result.stderr ?? ""}`.split("\n");
const reported: string[] = [];
let inV2Diagnostic = false;

for (const line of lines) {
  const isContinuation = /^\s/.test(line) && line.trim() !== "";
  if (isContinuation) {
    if (inV2Diagnostic) reported.push(line);
    continue;
  }
  inV2Diagnostic = V2_PATH.test(line);
  if (inV2Diagnostic) reported.push(line);
}

const errorCount = reported.filter((l) => !/^\s/.test(l)).length;

if (errorCount > 0) {
  console.error(reported.join("\n"));
  console.error(`\nFound ${errorCount} strictTemplates error(s) in src/v2.`);
  process.exit(1);
}

// A non-zero exit with no v2 diagnostics means vue-tsc itself failed.
if (result.status !== 0 && !lines.some((l) => /error TS/.test(l))) {
  console.error(result.stdout, result.stderr);
  process.exit(result.status ?? 1);
}

console.log("src/v2 passes strictTemplates.");
