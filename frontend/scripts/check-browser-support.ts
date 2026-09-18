/**
 * Fails when built CSS uses a feature the browser support floor does not cover
 * without an `@supports` fallback beside it.
 *
 * Runs over `dist/`, not source: Lightning CSS down-levels nesting, generates
 * vendor prefixes and rewrites colour functions from the same `.browserslistrc`
 * targets, so a source-level check reports features the build already repaired.
 * What survives into `dist/` is what actually ships.
 *
 * FEATURES is curated rather than derived from caniuse. A sweep of every
 * below-floor feature in this codebase is almost entirely `::-webkit-scrollbar`
 * rules, `cursor` keywords and mask prefixes, which degrade invisibly; listing
 * those would bury the handful that change a layout. Add an entry when a
 * feature genuinely breaks one.
 */
import fs from "node:fs";
import path from "node:path";
import postcss, { type Declaration, type Root, type Rule } from "postcss";

type Feature = {
  /** caniuse id, for the failure message. */
  id: string;
  /** Matches a declaration that uses the feature. */
  matches: (decl: Declaration) => boolean;
  /** Matches the `@supports` params of an acceptable fallback. */
  fallback: RegExp;
  /** Floor that covers it, for the failure message. */
  needs: string;
};

const FEATURES: Feature[] = [
  {
    id: "css-subgrid",
    matches: (decl) =>
      /^grid-template(-rows|-columns)?$/.test(decl.prop) &&
      /\bsubgrid\b/.test(decl.value),
    fallback: /\bsubgrid\b/,
    needs: "Chrome/Edge 117",
  },
];

/** Individual selectors of a rule, scoping attributes and all. */
function selectorsOf(rule: Rule): string[] {
  return rule.selectors.map((s) => s.replace(/\s+/g, " ").trim());
}

function inSupports(decl: Declaration): boolean {
  for (let node = decl.parent; node; node = node.parent as never) {
    if (
      node.type === "atrule" &&
      (node as { name: string }).name === "supports"
    )
      return true;
  }
  return false;
}

/** Selectors carrying a fallback under `@supports not (...)` in this sheet. */
function guardedSelectors(root: Root, feature: Feature): Set<string> {
  const guarded = new Set<string>();
  root.walkAtRules("supports", (atRule) => {
    if (!/^\s*not\b/.test(atRule.params)) return;
    if (!feature.fallback.test(atRule.params)) return;
    atRule.walkRules((rule) => {
      for (const selector of selectorsOf(rule)) guarded.add(selector);
    });
  });
  return guarded;
}

type Violation = { file: string; feature: Feature; selector: string };

function check(file: string, css: string): Violation[] {
  const root = postcss.parse(css, { from: file });
  const violations: Violation[] = [];

  for (const feature of FEATURES) {
    const guarded = guardedSelectors(root, feature);
    root.walkDecls((decl) => {
      if (!feature.matches(decl) || inSupports(decl)) return;
      const rule = decl.parent as Rule | undefined;
      if (rule?.type !== "rule") return;
      for (const selector of selectorsOf(rule)) {
        if (!guarded.has(selector))
          violations.push({ file, feature, selector });
      }
    });
  }
  return violations;
}

const distDir = path.join(import.meta.dirname, "..", "dist", "assets");
if (!fs.existsSync(distDir)) {
  console.error(
    `No build to check at ${distDir}. Run \`npm run build\` first.`,
  );
  process.exit(1);
}

const violations = fs
  .readdirSync(distDir)
  .filter((name) => name.endsWith(".css"))
  .flatMap((name) =>
    check(name, fs.readFileSync(path.join(distDir, name), "utf8")),
  );

if (violations.length === 0) {
  const ids = FEATURES.map((f) => f.id).join(", ");
  console.log(`Browser support floor upheld (checked: ${ids}).`);
  process.exit(0);
}

console.error(
  `${violations.length} selector(s) use a feature above the browser support ` +
    `floor with no \`@supports\` fallback:\n`,
);
for (const { file, feature, selector } of violations) {
  console.error(`  ${feature.id} (needs ${feature.needs})`);
  console.error(`    ${selector}`);
  console.error(`    in dist/assets/${file}\n`);
}
console.error(
  "Add an `@supports not (...)` fallback beside the rule, or raise the floor\n" +
    "in frontend/.browserslistrc if the feature is no longer above it.",
);
process.exit(1);
