// @ts-check

const VUEUSE_STORAGE = new Set(["useLocalStorage", "useStorage"]);
const GLOBAL_OBJECTS = new Set(["window", "globalThis", "self"]);

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow raw localStorage and vueuse's useLocalStorage/useStorage; store through the user-scoped helpers.",
    },
    schema: [],
    messages: {
      composable:
        "`{{name}}` is shared by every user on this browser: use `useUserLocalStorage` from @/composables/useUserLocalStorage.",
      global:
        "Raw `localStorage` is shared by every user on this browser: use `userStorage` from @/composables/useUserLocalStorage.",
    },
  },
  create(context) {
    return {
      ImportDeclaration(node) {
        if (node.source.value !== "@vueuse/core") return;
        for (const spec of node.specifiers) {
          if (
            spec.type === "ImportSpecifier" &&
            spec.imported.type === "Identifier" &&
            VUEUSE_STORAGE.has(spec.imported.name)
          ) {
            context.report({
              node: spec,
              messageId: "composable",
              data: { name: spec.imported.name },
            });
          }
        }
      },
      MemberExpression(node) {
        if (
          !node.computed &&
          node.property.type === "Identifier" &&
          node.property.name === "localStorage" &&
          node.object.type === "Identifier" &&
          GLOBAL_OBJECTS.has(node.object.name)
        ) {
          context.report({ node, messageId: "global" });
        }
      },
      "Program:exit"(node) {
        const globalScope = context.sourceCode.getScope(node);
        // Configured globals resolve to a global variable; the rest stay in `through`.
        const references = [
          ...(globalScope.set.get("localStorage")?.references ?? []),
          ...globalScope.through.filter(
            (ref) => ref.identifier.name === "localStorage",
          ),
        ];
        for (const ref of references) {
          context.report({ node: ref.identifier, messageId: "global" });
        }
      },
    };
  },
};
