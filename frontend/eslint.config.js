import eslint from "@eslint/js";
import prettierConfig from "eslint-config-prettier/flat";
import vue from "eslint-plugin-vue";
import vuea11y from "eslint-plugin-vuejs-accessibility";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  ...vuea11y.configs["flat/recommended"],
  // Global ignore (object with only `ignores` = applies everywhere).
  // Storybook config files live outside `src/` and aren't part of the
  // app tsconfig, so type-aware linting can't resolve them.
  {
    ignores: [
      ".storybook/**",
      "src/__generated__/**",
      // Build and coverage output: generated, so nothing here is fixable in
      // source. These only take effect in an `ignores`-only config object.
      "dist/**",
      "dist-ssr/**",
      "dev-dist/**",
      "storybook-static/**",
      "coverage/**",
    ],
  },
  {
    ignores: [
      "logs",
      "*.log",
      "npm-debug.log*",
      "yarn-debug.log*",
      "yarn-error.log*",
      "pnpm-debug.log*",
      "lerna-debug.log*",
      "node_modules",
      ".DS_Store",
      "*.local",
      "*.config.js",
      "src/plugins/*.d.ts",
    ],
    languageOptions: {
      parserOptions: {
        parser: "@typescript-eslint/parser",
        projectService: true,
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
      "vue/no-use-v-if-with-v-for": "off",
      "vue/component-name-in-template-casing": [
        "error",
        "PascalCase",
        {
          registeredComponentsOnly: true,
        },
      ],
      "vue/prop-name-casing": ["error", "camelCase"],
      "vue/attribute-hyphenation": ["error", "always"],
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
    },
  },
  // Keep last: Prettier owns formatting, so this switches off every
  // stylistic rule the two tools would otherwise fight over.
  prettierConfig,
);
