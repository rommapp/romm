// @ts-check
import noColorLiteral from "./rules/no-color-literal.js";
import noEmdashInComment from "./rules/no-emdash-in-comment.js";
import noLayoutMediaQuery from "./rules/no-layout-media-query.js";

/** @type {import("eslint").ESLint.Plugin} */
export default {
  meta: { name: "eslint-plugin-romm" },
  rules: {
    "no-color-literal": noColorLiteral,
    "no-emdash-in-comment": noEmdashInComment,
    "no-layout-media-query": noLayoutMediaQuery,
  },
};
