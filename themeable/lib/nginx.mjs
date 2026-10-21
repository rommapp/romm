// The one change to an upstream file: the nginx `location /assets` block learns to
// look in /themes/<theme>/ first. Done by anchored rewrite so a mismatch fails loudly.
import { COOKIE, STOCK_ID } from "./client.mjs";
import { PACK_ID, ROOT_FILES } from "./pack.mjs";

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

export function patchNginx(conf, defaultTheme = STOCK_ID) {
  if (conf.includes(MARKER)) throw new Error("template is already patched");
  if (defaultTheme !== STOCK_ID && !PACK_ID.test(defaultTheme)) throw new Error(`bad default theme "${defaultTheme}"`);
  const { start, end, indent, body } = findAssetsBlock(conf);
  const inner = `${indent}    `;

  const newBody = body
    .split("\n")
    .filter((line) => !/^\s*add_header Cache-Control /.test(line))
    .map((line) => line.replace(/try_files \$uri\b/, "try_files /themes/$themeable_theme$uri $uri"))
    .join("\n")
    .replace(/^\n/, "");

  const rootFiles = [...ROOT_FILES].map((f) => f.slice(1).replace(/\./g, "\\.")).join("|");
  const block =
    `${indent}${MARKER} favicons come from the visitor's theme when it ships them.\n` +
    `${indent}location ~ "^/(${rootFiles})$" {\n` +
    `${inner}add_header Cache-Control "no-cache";\n` +
    `${inner}add_header Vary Cookie;\n` +
    `${inner}try_files $themeable_root$uri $uri =404;\n` +
    `${indent}}\n\n` +
    `${indent}${MARKER} artwork comes from the active theme pack when it has the file.\n` +
    `${indent}# Responses depend on the ${COOKIE} cookie, so they revalidate instead of caching blind.\n` +
    `${indent}location /assets {\n` +
    `${inner}add_header Cache-Control "no-cache";\n` +
    `${inner}add_header Vary Cookie;\n` +
    `${newBody}}`;

  // The same-named query argument (set by preview tabs) wins over the cookie for that request only.
  const id = "[a-z0-9][a-z0-9-]{0,63}";
  const map =
    `${MARKER} theme id from the ${COOKIE} argument or cookie, limited to safe pack ids.\n` +
    `map "$arg_${COOKIE}:$cookie_${COOKIE}" $themeable_theme {\n` +
    `    default "${defaultTheme}";\n` +
    `    "~^(?<themeable_arg>${id}):" $themeable_arg;\n` +
    `    "~^[^:]*:(?<themeable_id>${id})$" $themeable_id;\n` +
    `}\n\n` +
    `${MARKER} favicons: the pack (or stock look) in the ${COOKIE} argument, else the cookie, else the server's theme.\n` +
    `map "$arg_${COOKIE}:$cookie_${COOKIE}" $themeable_root {\n` +
    `    default "/themeable/root";\n` +
    `    "~^${STOCK_ID}:" "/themeable/stock";\n` +
    `    "~^(?<themeable_root_arg>${id}):" "/themes/$themeable_root_arg/root";\n` +
    `    "~^[^:]*:${STOCK_ID}$" "/themeable/stock";\n` +
    `    "~^[^:]*:(?<themeable_root_id>${id})$" "/themes/$themeable_root_id/root";\n` +
    `}\n\n`;

  const patched = conf.slice(0, start) + block + conf.slice(end);
  const firstDirective = patched.search(/^(upstream|map|server)\b/m);
  if (firstDirective < 0) throw new Error("no top-level directive found to anchor the map");
  return patched.slice(0, firstDirective) + map + patched.slice(firstDirective);
}
