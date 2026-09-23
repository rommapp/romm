// @ts-check

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow the em dash (U+2014) in source, comments, and templates.",
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
        for (const match of sourceCode.text.matchAll(/\u2014/g)) {
          const index = match.index ?? 0;
          context.report({
            loc: {
              start: sourceCode.getLocFromIndex(index),
              end: sourceCode.getLocFromIndex(index + 1),
            },
            messageId: "emDash",
          });
        }
      },
    };
  },
};
