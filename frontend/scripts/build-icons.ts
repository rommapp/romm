// Writes the trimmed icon CSS. With --check it exits 1 if the committed file
// is stale instead of writing.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildIconAllowList,
  readSourceText,
  toLf,
  trimIconCss,
} from "./trim-mdi-fonts";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PACKAGE_CSS = resolve(
  ROOT,
  "node_modules/@mdi/font/css/materialdesignicons.css",
);
const OUTPUT = resolve(ROOT, "src/plugins/materialdesignicons-trimmed.css");

const HEADER = `/*
 * GENERATED FILE, do not hand-edit. Source: @mdi/font
 * Regenerate with: npm run build:icons
 */
`;

const countIcons = (css: string) => css.split("content:").length - 1;

const full = toLf(readFileSync(PACKAGE_CSS, "utf8"));
const allowList = buildIconAllowList(readSourceText(ROOT));
const trimmed = HEADER + trimIconCss(full, allowList);

const icons = countIcons(trimmed);
if (icons === 0) throw new Error("No icon rules survived, refusing to write.");

const kb = (bytes: number) => `${Math.round(bytes / 1024)} KB`;
const fullSize = Buffer.byteLength(full);
const trimmedSize = Buffer.byteLength(trimmed);
const percent = Math.round((1 - trimmedSize / fullSize) * 100);
const savedKb = ((fullSize - trimmedSize) / 1024).toFixed(1);
const summary =
  `${countIcons(full)} icons -> ${icons} icons | ` +
  `${kb(fullSize)} -> ${kb(trimmedSize)} | trimmed ${savedKb} KB (${percent}%)`;

const name = basename(OUTPUT);
const existing = existsSync(OUTPUT) ? toLf(readFileSync(OUTPUT, "utf8")) : "";
if (existing === trimmed) {
  console.log(`${name} up to date. ${summary}`);
} else if (process.argv.includes("--check")) {
  console.error(`${name} is stale. Run npm run build:icons and commit it.`);
  process.exit(1);
} else {
  writeFileSync(OUTPUT, trimmed);
  console.log(`${name} icons trimmed. ${summary}`);
}
