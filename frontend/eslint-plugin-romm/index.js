// @ts-check
import noColorLiteral from "./rules/no-color-literal.js";
import noLayoutMediaQuery from "./rules/no-layout-media-query.js";
import noSafeAreaEnv from "./rules/no-safe-area-env.js";
import noUnscopedLocalStorage from "./rules/no-unscoped-local-storage.js";

/** @type {import("eslint").ESLint.Plugin} */
export default {
  meta: { name: "eslint-plugin-romm" },
  rules: {
    "no-color-literal": noColorLiteral,
    "no-layout-media-query": noLayoutMediaQuery,
    "no-safe-area-env": noSafeAreaEnv,
    "no-unscoped-local-storage": noUnscopedLocalStorage,
  },
};
