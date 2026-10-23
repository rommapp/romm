// Reads RomM v2 design tokens out of CSS, either the generated
// frontend/src/v2/styles/tokens.css or a minified bundle from a built image.

/** Upstream selector (whitespace and quotes normalised) to pack scope name. */
export const SCOPE_SELECTORS = {
  ".r-v2": "common",
  ".r-v2.r-v2-dark": "dark",
  ".r-v2.r-v2-light": "light",
  "html[data-input=key] .r-v2": "input-key",
  "html[data-input=pad] .r-v2": "input-pad",
};

export const SCOPES = ["common", "dark", "light", "input-key", "input-pad"];

const TOKEN_NAME = /^--r-[a-z0-9-]+$/;

export function isTokenName(name) {
  return TOKEN_NAME.test(name);
}

function normaliseSelector(selector) {
  return selector.replace(/["']/g, "").replace(/\s+/g, " ").trim();
}

/** Splits a declaration block on semicolons that are not inside parentheses. */
function splitDeclarations(body) {
  const out = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < body.length; i++) {
    const ch = body[i];
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    else if (ch === ";" && depth === 0) {
      out.push(body.slice(start, i));
      start = i + 1;
    }
  }
  out.push(body.slice(start));
  return out;
}

/** Extracts --r-* custom properties as { <scope>: { name: value } } for each token scope. */
export function parseTokenCss(cssText) {
  const css = cssText.replace(/\/\*[\s\S]*?\*\//g, "");
  const scopes = Object.fromEntries(SCOPES.map((s) => [s, {}]));
  const rule = /([^{}@;]+)\{([^{}]*)\}/g;
  let match;
  while ((match = rule.exec(css)) !== null) {
    const selectors = match[1].split(",").map(normaliseSelector);
    for (const selector of selectors) {
      const scope = SCOPE_SELECTORS[selector];
      if (!scope) continue;
      for (const decl of splitDeclarations(match[2])) {
        const colon = decl.indexOf(":");
        if (colon < 0) continue;
        const name = decl.slice(0, colon).trim();
        if (!isTokenName(name)) continue;
        scopes[scope][name] = decl
          .slice(colon + 1)
          .replace(/\s+/g, " ")
          .trim();
      }
    }
  }
  return scopes;
}

/** Group label for a token, used by the catalog and the theme editor. */
export function tokenGroup(name) {
  const parts = name.replace(/^--r-/, "").split("-");
  if (parts[0] === "color") {
    const known = ["brand", "status", "provider", "overlay", "canvas", "crt", "cover", "romm"];
    return known.includes(parts[1]) ? `color-${parts[1]}` : "color-surface";
  }
  if (parts[0] === "font") return `font-${parts[1] ?? "other"}`;
  return parts[0];
}

/** All token names across scopes, sorted. */
export function allTokenNames(scopes) {
  const names = new Set();
  for (const scope of Object.values(scopes)) {
    for (const name of Object.keys(scope)) names.add(name);
  }
  return [...names].sort();
}
