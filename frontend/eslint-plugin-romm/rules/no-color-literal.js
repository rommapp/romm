// @ts-check
import { sfcStyleBlocks } from "../utils/sfcStyles.js";

// A declaration follows `{`, `;` or a nested block's `}` and ends at `;` or
// `}`. A selector ends at `{`, so `a:not(#abc) {` is never read as a value.
const DECLARATION = /(?<=[{;}]\s*)(--[\w-]+|[a-z-]+)\s*:([^;{}]*)(?=[;}])/gi;
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
        const { sourceCode } = context;
        for (const block of sfcStyleBlocks(context)) {
          for (const decl of block.text.matchAll(DECLARATION)) {
            const value = decl[2];
            const valueStart =
              block.start + (decl.index ?? 0) + decl[0].length - value.length;
            const scanned = value.replace(URL_OR_STRING, (u) =>
              " ".repeat(u.length),
            );
            for (const hit of scanned.matchAll(COLOR_LITERAL)) {
              const index = valueStart + (hit.index ?? 0);
              context.report({
                loc: {
                  start: sourceCode.getLocFromIndex(index),
                  end: sourceCode.getLocFromIndex(index + hit[0].length),
                },
                messageId: "colorLiteral",
                data: { literal: hit[0] },
              });
            }
          }
        }
      },
    };
  },
};
