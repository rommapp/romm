// @ts-check

// An icon name cut off right where a value is appended, such as "mdi-" or "mdi-home-".
const PARTIAL_NAME = /(?:^|[^a-z0-9-])mdi-[a-z0-9-]*$/;

/** @param {import("estree").Node} node */
function isStringLiteral(node) {
  return node.type === "Literal" && typeof node.value === "string";
}

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow building an mdi-* icon name at runtime; the build keeps only icons named in full in src/.",
    },
    schema: [],
    messages: {
      dynamic:
        "Name every icon in full (a lookup object of `mdi-*` strings): the build drops glyphs for icon names it cannot find in src/.",
    },
  },
  create(context) {
    const visitor = {
      /** @param {import("estree").TemplateLiteral} node */
      TemplateLiteral(node) {
        const prefixes = node.quasis.slice(0, -1);
        if (
          prefixes.some((quasi) => PARTIAL_NAME.test(quasi.value.cooked ?? ""))
        ) {
          context.report({ node, messageId: "dynamic" });
        }
      },
      /** @param {import("estree").BinaryExpression} node */
      BinaryExpression(node) {
        if (node.operator !== "+" || isStringLiteral(node.right)) return;
        if (
          isStringLiteral(node.left) &&
          PARTIAL_NAME.test(String(node.left.value))
        ) {
          context.report({ node, messageId: "dynamic" });
        }
      },
    };
    const services = context.sourceCode.parserServices;
    if (!services?.defineTemplateBodyVisitor) return visitor;
    return services.defineTemplateBodyVisitor(visitor, visitor);
  },
};
