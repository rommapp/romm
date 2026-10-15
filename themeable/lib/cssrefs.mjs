// Finds CSS rules in upstream source that point at /assets/ artwork. Vite inlines
// small files as data: URIs, so those rules never request the URL and nginx can't
// swap them; the compiler re-points each rule at the pack's file instead.
import { readFileSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ASSET_URL = /url\(\s*["']?(\/assets\/[A-Za-z0-9_./-]+)["']?\s*\)/g;

/** Walks CSS text and yields leaf rules with their enclosing preludes. */
export function leafRules(css) {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  const stack = [];
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "{") {
      stack.push({ prelude: text.slice(start, i).trim(), bodyStart: i + 1, hasChild: false });
      if (stack.length > 1) stack[stack.length - 2].hasChild = true;
      start = i + 1;
    } else if (ch === "}") {
      const node = stack.pop();
      if (node && !node.hasChild) {
        out.push({
          ancestors: stack.map((s) => s.prelude),
          selector: node.prelude,
          body: text.slice(node.bodyStart, i),
        });
      }
      start = i + 1;
    } else if (ch === ";") {
      start = i + 1;
    }
  }
  return out;
}

function declarations(body) {
  return body
    .split(";")
    .map((d) => d.trim())
    .filter(Boolean)
    .map((d) => {
      const colon = d.indexOf(":");
      return colon < 0 ? null : { property: d.slice(0, colon).trim(), value: d.slice(colon + 1).trim() };
    })
    .filter(Boolean);
}

/** Every declaration that uses an /assets/ url, keyed by asset path. */
export function findCssReferences(css, file) {
  const refs = {};
  for (const rule of leafRules(css)) {
    if (rule.selector.startsWith("@")) continue;
    if (rule.ancestors.some((a) => !a.startsWith("@"))) continue;
    for (const { property, value } of declarations(rule.body)) {
      const urls = [...value.matchAll(ASSET_URL)].map((m) => m[1]);
      for (const asset of new Set(urls)) {
        (refs[asset] ??= []).push({
          file,
          atRules: rule.ancestors,
          selector: rule.selector.replace(/\s+/g, " "),
          property,
          value: value.replace(/\s+/g, " "),
        });
      }
    }
  }
  return refs;
}

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

/** Scans .css files and .vue <style> blocks under srcDir. */
export function scanCssReferences(srcDir) {
  const all = {};
  for (const file of walk(srcDir)) {
    let css = "";
    if (file.endsWith(".css")) css = readFileSync(file, "utf8");
    else if (file.endsWith(".vue")) {
      const text = readFileSync(file, "utf8");
      css = [...text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join("\n");
    } else continue;
    if (!css.includes("/assets/")) continue;
    const rel = relative(srcDir, file).split(sep).join("/");
    for (const [asset, list] of Object.entries(findCssReferences(css, rel))) {
      (all[asset] ??= []).push(...list);
    }
  }
  return Object.fromEntries(Object.entries(all).sort(([a], [b]) => a.localeCompare(b)));
}

/** Prefixes each selector in a list with the theme scope. */
export function scopeSelectorList(selector, scope) {
  return selector
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => (/^(html|:root)\b/.test(s) ? s.replace(/^(html|:root)/, scope) : `${scope} ${s}`))
    .join(",\n");
}
