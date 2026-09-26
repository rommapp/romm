// @ts-check
import { reportAt } from "../utils/report.js";
import { rangeOf, sfcStyleRoots } from "../utils/sfcStyles.js";

const URL_OR_STRING = /url\([^)]*\)|"[^"]*"|'[^']*'/gi;
const COLOR_LITERAL =
  /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|device-cmyk)\(/gi;

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow hex and color-function literals in SFC styles; use a --r-color-* token or color-mix().",
    },
    schema: [],
    messages: {
      colorLiteral:
        "Color literal `{{literal}}`: use a `var(--r-color-*)` token, or `color-mix()` over a token or named color. Add a token in src/v2/tokens/index.ts if none fits.",
    },
  },
  create(context) {
    return {
      Program() {
        for (const block of sfcStyleRoots(context)) {
          block.root.walkDecls((decl) => {
            const value = decl.raws.value?.raw ?? decl.value;
            const valueStart =
              rangeOf(block, decl)[0] +
              decl.prop.length +
              (decl.raws.between ?? "").length;
            const scanned = value.replace(URL_OR_STRING, (u) =>
              " ".repeat(u.length),
            );
            for (const hit of scanned.matchAll(COLOR_LITERAL)) {
              reportAt(
                context,
                valueStart + (hit.index ?? 0),
                hit[0].length,
                "colorLiteral",
                { literal: hit[0] },
              );
            }
          });
        }
      },
    };
  },
};
