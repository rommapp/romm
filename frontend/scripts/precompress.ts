/**
 * precompress — a build plugin that writes a .gz sibling for each built asset.
 *
 * nginx serves these directly via `gzip_static`, so the bundle is compressed
 * once at build time rather than on every cold page load.
 *
 * Level 9 is affordable because it runs once. The ratio lands within a percent
 * of what nginx produces at runtime, so the win is the CPU, not the bytes.
 * Files without a .gz sibling still fall back to on-the-fly gzip.
 */
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";
import { constants, gzipSync } from "node:zlib";
import type { Plugin } from "vite";

// Kept in step with gzip_types in docker/nginx/default.conf. Formats that are
// already compressed (png, woff2, ico) only grow, so they are left alone.
const COMPRESSIBLE = new Set([
  ".css",
  ".html",
  ".js",
  ".json",
  ".map",
  ".mjs",
  ".svg",
  ".txt",
  ".wasm",
  ".webmanifest",
  ".xml",
]);

// nginx's gzip_min_length: below this the encoding overhead outweighs the win.
const MIN_BYTES = 1024;

async function* walk(dir: string): AsyncGenerator<string> {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else if (entry.isFile()) yield path;
  }
}

export function precompress(): Plugin {
  let outDir = "";

  return {
    name: "romm:precompress",
    apply: "build",
    // `post` so the service worker vite-plugin-pwa emits is compressed too.
    enforce: "post",

    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },

    async closeBundle() {
      let raw = 0;
      let packed = 0;
      let count = 0;

      for await (const path of walk(outDir)) {
        if (!COMPRESSIBLE.has(extname(path))) continue;
        const { size } = await stat(path);
        if (size < MIN_BYTES) continue;

        const gzipped = gzipSync(await readFile(path), {
          level: constants.Z_BEST_COMPRESSION,
        });
        // A .gz larger than its source would make nginx serve the worse one.
        if (gzipped.byteLength >= size) continue;

        await writeFile(`${path}.gz`, gzipped);
        raw += size;
        packed += gzipped.byteLength;
        count += 1;
      }

      const mib = (bytes: number) => (bytes / 1024 ** 2).toFixed(1);
      this.info(
        `${count} files, ${mib(raw)} MiB -> ${mib(packed)} MiB ` +
          `(${Math.round((1 - packed / raw) * 100)}% smaller)`,
      );
    },
  };
}
