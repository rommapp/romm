// @ts-check
import { readFileSync } from "node:fs";
import { reportAt } from "../utils/report.js";
import { rangeOf, styleRoots } from "../utils/sfcStyles.js";

const TOKENS_CSS = new URL("../../src/v2/styles/tokens.css", import.meta.url);
const SPACING_PROP =
  /^(?:(?:row-|column-)?gap|(?:margin|padding|inset)(?:-[a-z]+)*)$/i;
const IGNORED = /\/\*[\s\S]*?\*\/|url\([^)]*\)|"[^"]*"|'[^']*'/gi;
const PX_LENGTH = /(?<![\w.-])(-?)(\d*\.?\d+)px(?![\w-])/gi;

/** @type {Map<number, string> | undefined} */
let scale;

/**
 * The `--r-space-*` scale as px value to custom property name.
 * @returns {Map<number, string>}
 */
function spaceScale() {
  scale ??= new Map(
    [
      ...readFileSync(TOKENS_CSS, "utf8").matchAll(
        /(--r-space-[\w-]+):\s*(\d*\.?\d+)px;/g,
      ),
    ].map((m) => [Number(m[2]), m[1]]),
  );
  return scale;
}

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "suggestion",
    fixable: "code",
    docs: {
      description:
        "Disallow px literals in gap, margin, padding, and inset when a --r-space-* token has the same value.",
    },
    schema: [],
    messages: {
      spacingLiteral: "Spacing literal `{{literal}}`: use `{{replacement}}`.",
    },
  },
  create(context) {
    const scale = spaceScale();
    return {
      Program() {
        for (const block of styleRoots(context)) {
          block.root.walkDecls((decl) => {
            if (!SPACING_PROP.test(decl.prop)) return;
            const value = decl.raws.value?.raw ?? decl.value;
            const valueStart =
              rangeOf(block, decl)[0] +
              decl.prop.length +
              (decl.raws.between ?? "").length;
            const scanned = value.replace(IGNORED, (u) => " ".repeat(u.length));
            for (const hit of scanned.matchAll(PX_LENGTH)) {
              const token = scale.get(Number(hit[2]));
              if (!token) continue;
              const replacement = hit[1]
                ? `calc(-1 * var(${token}))`
                : `var(${token})`;
              const start = valueStart + (hit.index ?? 0);
              reportAt(
                context,
                start,
                hit[0].length,
                "spacingLiteral",
                { literal: hit[0], replacement },
                (fixer) =>
                  fixer.replaceTextRange(
                    [start, start + hit[0].length],
                    replacement,
                  ),
              );
            }
          });
        }
      },
    };
  },
};
