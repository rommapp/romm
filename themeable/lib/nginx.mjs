// The one change to an upstream file: the nginx `location /assets` block learns to
// look in /themes/<theme>/ first. Done by anchored rewrite so a mismatch fails loudly.
import { PACK_ID } from "./pack.mjs";

export const MARKER = "# themeable:";

/** Finds the single `location /assets { ... }` block (not /assets/romm/... or the regex location). */
export function findAssetsBlock(conf) {
  const re = /^([ \t]*)location \/assets \{([^{}]*)\}/gm;
  const matches = [...conf.matchAll(re)];
  if (matches.length !== 1) {
    throw new Error(`expected exactly one "location /assets {" block, found ${matches.length}`);
  }
  const m = matches[0];
  if (!/try_files \$uri\b/.test(m[2])) throw new Error('the /assets block no longer uses "try_files $uri"');
  return { start: m.index, end: m.index + m[0].length, indent: m[1], body: m[2] };
}

export function patchNginx(conf, defaultTheme = "none") {
  if (conf.includes(MARKER)) throw new Error("template is already patched");
  if (defaultTheme !== "none" && !PACK_ID.test(defaultTheme)) throw new Error(`bad default theme "${defaultTheme}"`);
  const { start, end, indent, body } = findAssetsBlock(conf);
  const inner = `${indent}    `;

  const newBody = body
    .split("\n")
    .filter((line) => !/^\s*add_header Cache-Control /.test(line))
    .map((line) => line.replace(/try_files \$uri\b/, "try_files /themes/$themeable_theme$uri $uri"))
    .join("\n")
    .replace(/^\n/, "");

  const block =
    `${indent}${MARKER} artwork comes from the active theme pack when it has the file.\n` +
    `${indent}# Responses depend on the romm_theme cookie, so they revalidate instead of caching blind.\n` +
    `${indent}location /assets {\n` +
    `${inner}add_header Cache-Control "no-cache";\n` +
    `${inner}add_header Vary Cookie;\n` +
    `${newBody}}`;

  const map =
    `${MARKER} theme id from the romm_theme cookie, limited to safe pack ids.\n` +
    `map $cookie_romm_theme $themeable_theme {\n` +
    `    default "${defaultTheme}";\n` +
    `    "~^(?<themeable_id>[a-z0-9][a-z0-9-]{0,63})$" $themeable_id;\n` +
    `}\n\n`;

  const patched = conf.slice(0, start) + block + conf.slice(end);
  const firstDirective = patched.search(/^(upstream|map|server)\b/m);
  if (firstDirective < 0) throw new Error("no top-level directive found to anchor the map");
  return patched.slice(0, firstDirective) + map + patched.slice(firstDirective);
}
