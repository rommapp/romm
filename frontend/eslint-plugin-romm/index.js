// @ts-check
import noColorLiteral from "./rules/no-color-literal.js";
import noEmDash from "./rules/no-em-dash.js";
import noLayoutMediaQuery from "./rules/no-layout-media-query.js";

/** @type {import("eslint").ESLint.Plugin} */
export default {
  meta: { name: "eslint-plugin-romm" },
  rules: {
    "no-color-literal": noColorLiteral,
    "no-em-dash": noEmDash,
    "no-layout-media-query": noLayoutMediaQuery,
  },
};
