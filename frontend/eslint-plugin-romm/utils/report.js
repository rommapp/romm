// @ts-check

/**
 * Report a problem over `length` characters starting at a source offset.
 * @param {import("eslint").Rule.RuleContext} context
 * @param {number} index
 * @param {number} length
 * @param {string} messageId
 * @param {Record<string, string>} [data]
 */
export function reportAt(context, index, length, messageId, data) {
  const { sourceCode } = context;
  context.report({
    loc: {
      start: sourceCode.getLocFromIndex(index),
      end: sourceCode.getLocFromIndex(index + length),
    },
    messageId,
    data,
  });
}
