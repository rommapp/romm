#!/usr/bin/env node
// Zips each folder pack in --packs into --out/<id>.zip; the image build runs it on the built-in packs.
import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { findPacks, zipFolderPack, ZIP_EXT } from "../lib/packfiles.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const args = parseArgs();
const packsDir = resolve(args.packs ?? join(here, "..", "packs"));
if (!args.out) fail("pass --out <dir>");
const outDir = resolve(args.out);
// The output folder is replaced, so it must not hold the packs themselves.
if (packsDir === outDir || packsDir.startsWith(`${outDir}/`)) fail(`--out ${outDir} would delete the packs in ${packsDir}`);

const folders = findPacks(packsDir).filter((p) => p.format === "folder");
if (!folders.length) fail(`no folder packs in ${packsDir}`);
rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });
for (const { id, path } of folders) zipFolderPack(path, join(outDir, `${id}${ZIP_EXT}`));
console.log(`themeable: zipped ${folders.length} pack(s) [${folders.map((p) => p.id).join(", ")}] -> ${outDir}`);
