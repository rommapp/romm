let eslint = require("@eslint/js");
let tseslint = require("typescript-eslint");
let globals = require("globals");
let vue = require("eslint-plugin-vue");

module.exports = tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  {
    ignores: ["node_modules", "dist", "__generated__", "**/*.config.js"],
    languageOptions: {
      parserOptions: {
        parser: "@typescript-eslint/parser",
        project: "./tsconfig.json",
        ecmaVersion: 2022,
        extraFileExtensions: [".vue"],
      },
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/valid-v-slot": "off",
      "vue/no-mutating-props": "off",
    },
  },
);
