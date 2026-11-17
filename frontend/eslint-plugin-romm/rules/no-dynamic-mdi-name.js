// @ts-check

// An icon name cut off right where a value is appended, such as "mdi-" or "mdi-home-".
// Keep [a-z0-9-] in step with ICON_NAME in scripts/trimMdiIcons.ts.
const PARTIAL_NAME = /(?:^|[^\w-])mdi-[a-z0-9-]*$/;
// Appended text that ends the name before it, as in "mdi-home" + " " + tone.
const NAME_END = /^[^a-z0-9-]/;

/**
 * The static text at one end of a concatenated string, or "" when that end is a runtime value.
 * @param {import("estree").Node} node
 * @param {"start" | "end"} side
 * @returns {string}
 */
function edgeText(node, side) {
  if (node.type === "Literal" && typeof node.value === "string") {
    return node.value;
  }
  if (node.type === "TemplateLiteral") {
    const quasi = side === "start" ? node.quasis[0] : node.quasis.at(-1);
    return quasi?.value.cooked ?? "";
  }
  if (node.type === "BinaryExpression" && node.operator === "+") {
    return edgeText(side === "start" ? node.left : node.right, side);
  }
  return "";
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
        "Name every icon in full (a lookup object of `mdi-*` strings): the build drops the CSS of icon names it cannot find in src/.",
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
        if (
          node.operator === "+" &&
          PARTIAL_NAME.test(edgeText(node.left, "end")) &&
          !NAME_END.test(edgeText(node.right, "start"))
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
