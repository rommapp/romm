import { mkdtemp, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { precompress } from "../scripts/precompress";

/** Run the plugin's build hooks against a throwaway output directory. */
async function runOn(outDir: string): Promise<void> {
  const plugin = precompress();
  const { configResolved, closeBundle } = plugin as unknown as {
    configResolved: (config: unknown) => void;
    closeBundle: (this: { info: (msg: string) => void }) => Promise<void>;
  };
  configResolved({ root: outDir, build: { outDir } });
  await closeBundle.call({ info: () => {} });
}

async function fixture(
  files: Record<string, string | Buffer>,
): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "precompress-"));
  for (const [name, body] of Object.entries(files)) {
    await mkdir(join(dir, name, ".."), { recursive: true });
    await writeFile(join(dir, name), body);
  }
  return dir;
}

describe("precompress", () => {
  it("only runs on builds, after the other plugins have emitted", () => {
    const plugin = precompress();
    expect(plugin.apply).toBe("build");
    expect(plugin.enforce).toBe("post");
  });

  it("writes a .gz sibling whose contents round-trip", async () => {
    const body = "const compressible = 1;\n".repeat(200);
    const dir = await fixture({ "assets/app.js": body });

    await runOn(dir);

    const gz = await readFile(join(dir, "assets/app.js.gz"));
    expect(gunzipSync(gz).toString()).toBe(body);
    expect(gz.byteLength).toBeLessThan(Buffer.byteLength(body));
  });

  it("skips files below the gzip_min_length nginx uses", async () => {
    const dir = await fixture({ "tiny.css": "a{color:red}" });

    await runOn(dir);

    expect(await readdir(dir)).not.toContain("tiny.css.gz");
  });

  it("leaves already-compressed formats alone", async () => {
    const dir = await fixture({ "logo.png": Buffer.alloc(4096, 7) });

    await runOn(dir);

    expect(await readdir(dir)).not.toContain("logo.png.gz");
  });

  it("does not compress its own output on a second run", async () => {
    const dir = await fixture({
      "app.js": "const compressible = 1;\n".repeat(200),
    });

    await runOn(dir);
    await runOn(dir);

    expect(await readdir(dir)).not.toContain("app.js.gz.gz");
  });
});
