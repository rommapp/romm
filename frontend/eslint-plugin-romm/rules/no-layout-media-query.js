// @ts-check
import { sfcStyleBlocks } from "../utils/sfcStyles.js";

const MEDIA_RULE = /@media\b([^{;]*)/gi;
// Whatever is left after removing these is a condition the rule rejects.
const ALLOWED_PARTS =
  /\(\s*prefers-reduced-motion\b[^)]*\)|\b(?:print|screen|all|only|not|and)\b|[\s,]/gi;

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow @media in SFC styles except prefers-reduced-motion and print; layout switches use html[data-bp~=...].",
    },
    schema: [],
    messages: {
      layoutMedia:
        'Use `html[data-bp~="..."]` selectors (useBreakpoint) for layout. Only `prefers-reduced-motion` and `print` media queries are allowed.',
    },
  },
  create(context) {
    return {
      Program() {
        const { sourceCode } = context;
        for (const block of sfcStyleBlocks(context)) {
          for (const rule of block.text.matchAll(MEDIA_RULE)) {
            if (rule[1].replace(ALLOWED_PARTS, "") === "") continue;
            const index = block.start + (rule.index ?? 0);
            context.report({
              loc: {
                start: sourceCode.getLocFromIndex(index),
                end: sourceCode.getLocFromIndex(
                  index + rule[0].trimEnd().length,
                ),
              },
              messageId: "layoutMedia",
            });
          }
        }
      },
    };
  },
};
