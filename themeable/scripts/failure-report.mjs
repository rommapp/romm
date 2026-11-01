#!/usr/bin/env node
// Turns `gh run view --log-failed` output (stdin) into a short Markdown list of what broke, per job.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

// Lines that name a failure: failed tests, thrown errors, failed checks and the runner's own errors.
const FAILURE = /✖ (?!failing tests)|\bError:|AssertionError|^FAIL |::error|themeable: .*(failed|refused|could not|couldn't)/;
const PER_JOB = 15;

/** Groups failure lines by job; `root` (the checkout path) is cut so paths read as repository paths. */
export function failureReport(log, { root = "" } = {}) {
  const jobs = new Map();
  for (const raw of log.split("\n")) {
    const [job, , rest] = raw.split("\t");
    if (rest === undefined) continue;
    const line = rest
      .replace(/^\S+Z /, "")
      .replace("##[error]", "")
      .replaceAll(root ? `${root}/` : "\0", "")
      .trimEnd();
    if (!line.trim() || !(FAILURE.test(line) || rest.includes("##[error]"))) continue;
    if (!jobs.has(job)) jobs.set(job, new Set());
    jobs.get(job).add(line.trim());
  }
  if (!jobs.size) return "_No failure lines found in the logs; open the run for details._";
  return [...jobs]
    .map(([job, lines]) => {
      const shown = [...lines].slice(0, PER_JOB);
      const more = lines.size > PER_JOB ? `\n- …and ${lines.size - PER_JOB} more` : "";
      return `### ${job}\n\n${shown.map((l) => `- \`${l.replaceAll("`", "'")}\``).join("\n")}${more}`;
    })
    .join("\n\n");
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(failureReport(readFileSync(0, "utf8"), { root: process.env.GITHUB_WORKSPACE ?? "" }) + "\n");
}
