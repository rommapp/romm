// @ts-check
import { sfcFragment, sfcStyleCommentRanges } from "../utils/sfcStyles.js";

/**
 * Source ranges of every comment: script, SFC template, and SFC style.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {[number, number][]}
 */
function commentRanges(context) {
  const { sourceCode } = context;
  /** @type {[number, number][]} */
  const ranges = sourceCode
    .getAllComments()
    .flatMap((c) =>
      c.range ? [/** @type {[number, number]} */ (c.range)] : [],
    );
  for (const c of sfcFragment(context)?.comments ?? []) ranges.push(c.range);
  ranges.push(...sfcStyleCommentRanges(context));
  return ranges;
}

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow the em dash (U+2014) in comments (script, template, and style). Strings and template text are code and stay allowed.",
    },
    schema: [],
    messages: {
      emDash:
        "Replace the em dash with a comma, parentheses, or a separate sentence.",
    },
  },
  create(context) {
    return {
      Program() {
        const { sourceCode } = context;
        const { text } = sourceCode;
        for (const [start, end] of commentRanges(context)) {
          let index = text.indexOf("\u2014", start);
          while (index !== -1 && index < end) {
            context.report({
              loc: {
                start: sourceCode.getLocFromIndex(index),
                end: sourceCode.getLocFromIndex(index + 1),
              },
              messageId: "emDash",
            });
            index = text.indexOf("\u2014", index + 1);
          }
        }
      },
    };
  },
};
