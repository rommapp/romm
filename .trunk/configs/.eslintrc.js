/* eslint-disable */

let eslint = require("@eslint/js");
let tseslint = require("typescript-eslint");
let globals = require("globals");
let vue = require("eslint-plugin-vue");

module.exports = tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  {
    ignores: ["node_modules", "dist", "__generated__", "*.config.js"],
    languageOptions: {
      parser: "vue-eslint-parser",
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
      // Vuetify supports modifier syntax of { [x: `item.${string}`]: ... }
      "vue/valid-v-slot": "off",
    },
  },
);
