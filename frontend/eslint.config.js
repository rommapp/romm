import eslint from "@eslint/js";
import prettierConfig from "eslint-config-prettier/flat";
import { createTypeScriptImportResolver } from "eslint-import-resolver-typescript";
import importX from "eslint-plugin-import-x";
import vue from "eslint-plugin-vue";
import vuea11y from "eslint-plugin-vuejs-accessibility";
import globals from "globals";
import tseslint from "typescript-eslint";
import romm from "./eslint-plugin-romm/index.js";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  ...vuea11y.configs["flat/recommended"],
  importX.flatConfigs.recommended,
  importX.flatConfigs.typescript,
  {
    // Only the cycle rule below earns its keep; the rest of the preset
    // re-reports what vue-tsc already catches, at a module graph per rule.
    rules: {
      "import-x/no-unresolved": "off",
      "import-x/named": "off",
      "import-x/namespace": "off",
      "import-x/default": "off",
      "import-x/export": "off",
      "import-x/no-named-as-default": "off",
      "import-x/no-named-as-default-member": "off",
    },
  },
  // Global ignore (object with only `ignores` = applies everywhere).
  {
    ignores: [
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
  // Import cycles. The resolver has to be the one that reads tsconfig `paths`,
  // or `@/*` and `@v2/*` go unresolved and the rule silently passes.
  {
    files: ["src/**/*.ts", "src/**/*.vue"],
    settings: {
      "import-x/resolver-next": [
        createTypeScriptImportResolver({
          project: "./tsconfig.json",
          extensions: [".ts", ".d.ts", ".tsx", ".vue", ".js", ".mjs", ".json"],
        }),
      ],
    },
    rules: {
      // Lazy route components make the router reachable from the views it
      // renders; that edge is resolved at runtime, so it is not a real cycle.
      "import-x/no-cycle": [
        "error",
        {
          maxDepth: 15,
          allowUnsafeDynamicCyclicDependency: true,
          ignoreExternal: true,
        },
      ],
    },
  },
  // typescript-eslint scopes these TS-redundant core rules to .ts files only.
  { ...tseslint.configs.eslintRecommended, files: ["**/*.vue"] },
  {
    // Frozen v1: two cycles between the console theme helpers predate the
    // rule and cannot be refactored under the freeze.
    files: ["src/console/**"],
    rules: { "import-x/no-cycle": "off" },
  },
  // v2 primitives: no stores, services, i18n, emitter, or product domain.
  {
    files: ["src/v2/lib/**/*.ts", "src/v2/lib/**/*.vue"],
    ignores: ["**/*.stories.ts", "**/*.test.ts", "**/*.spec.ts"],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "pinia", message: "Primitives take state via props." },
            {
              name: "vue-i18n",
              message:
                "Primitives take text via props, slots, or useChromeLabels().",
            },
            { name: "axios", message: "Primitives do not fetch." },
            {
              name: "vue-router",
              importNames: ["useRouter", "useRoute"],
              message: "Primitives accept a RouterLink `to`, not the router.",
            },
          ],
        },
      ],
      // Matches resolved files, so every alias and relative spelling is covered.
      "import-x/no-restricted-paths": [
        "error",
        {
          zones: [
            {
              from: ["./src/services", "./src/stores"],
              message:
                "Primitives do not use services or stores; move this to a shared or feature composite.",
            },
            {
              from: "./src/__generated__",
              message:
                "Backend types are product domain; primitives take generic props.",
            },
            {
              from: "./src/types/emitter.d.ts",
              message: "Primitives do not use the emitter.",
            },
            {
              from: "./src/locales",
              message:
                "Primitives take text via props, slots, or useChromeLabels().",
            },
            {
              from: "./src/plugins/router.ts",
              message: "Primitives accept a RouterLink `to`, not the router.",
            },
            {
              from: [
                "./src/v2/components",
                "./src/v2/composables/usePlatformIconCache",
              ],
              message:
                "Primitives cannot depend on composites or domain composables.",
            },
          ].map((zone) => ({ target: "./src/v2/lib", ...zone })),
        },
      ],
    },
  },
  // v2 SFC shape, from the frontend-v2-components skill.
  {
    files: ["src/v2/**/*.vue"],
    rules: {
      "vue/block-lang": ["error", { script: { lang: "ts" } }],
      "vue/component-api-style": ["error", ["script-setup"]],
      "vue/block-order": [
        "error",
        {
          order: ["script", "template", "style[scoped]", "style:not([scoped])"],
        },
      ],
      "vue/define-props-declaration": ["error", "type-based"],
      "vue/define-emits-declaration": ["error", "type-based"],
    },
  },
  // Repo rules without a stock equivalent live in ./eslint-plugin-romm.
  {
    files: ["src/v2/**/*.ts", "src/v2/**/*.vue"],
    plugins: { romm },
    rules: {
      "romm/no-emdash-in-comment": "error",
      "romm/no-color-literal": "error",
      "romm/no-layout-media-query": "error",
    },
  },
  // Keep last: Prettier owns formatting, so this switches off every
  // stylistic rule the two tools would otherwise fight over.
  prettierConfig,
);
