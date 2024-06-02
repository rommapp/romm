let eslint = require("@eslint/js");
let tseslint = require("typescript-eslint");

let vuRecommended = require("eslint-plugin-vue").configs["flat/recommended"];

module.exports = tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...vuRecommended,
  {
    languageOptions: {
      parserOptions: {
        ...vuRecommended.parserOptions,
        parser: "@typescript-eslint/parser",
      },
    },
  },
);
