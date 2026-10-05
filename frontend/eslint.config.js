import eslint from "@eslint/js";
import { vueTsConfigs, withVueTs } from "@vue/eslint-config-typescript";
import prettierConfig from "eslint-config-prettier/flat";
import { createTypeScriptImportResolver } from "eslint-import-resolver-typescript";
import importX from "eslint-plugin-import-x";
import vue from "eslint-plugin-vue";
import vuea11y from "eslint-plugin-vuejs-accessibility";
import globals from "globals";
import romm from "./eslint-plugin-romm/index.js";
import e2eConfig from "./eslint.e2e.config.js";

// Heavy modules that belong in a lazy chunk; add the next one here.
const heavyImports = [
  {
    group: ["md-editor-v3", "md-editor-v3/**"],
    allowTypeImports: true,
    message:
      "md-editor-v3 is heavy; render it through @/v2/components/shared/asyncMarkdown.",
  },
  {
    group: [
      "**/markdownPreview",
      "**/markdownEditor",
      "**/MarkdownViewer.vue",
      "**/mdeditor",
    ],
    allowTypeImports: true,
    message:
      "This module bundles md-editor-v3; import it only from a lazy chunk.",
  },
];

const romCastRule = {
  selector:
    "TSAsExpression:matches([typeAnnotation.typeName.name=/^(SimpleRom|DetailedRom|SimpleRomSchema|DetailedRomSchema|RomFileSchema|RomUserSchema|RomMetadataSchema)$/], [typeAnnotation.elementType.typeName.name=/^(SimpleRom|DetailedRom|SimpleRomSchema|DetailedRomSchema|RomFileSchema)$/], [typeAnnotation.objectType.typeName.name=/^(SimpleRom|DetailedRom|SimpleRomSchema|DetailedRomSchema)$/])",
  message:
    "Build ROM fixtures with romFixture or detailedRomFixture from @/utils/rom.fixtures instead of a cast.",
};

const platformCastRule = {
  selector:
    "TSAsExpression[typeAnnotation.typeName.name=/^(Platform|PlatformSchema)$/]",
  message:
    "Build platform fixtures with platformFixture from @/utils/platform.fixtures instead of a cast.",
};

// Only object literals: reading a value back as one of these types is fine.
const modelCastRule = {
  selector:
    ":matches(TSAsExpression[expression.type='ObjectExpression'], TSAsExpression[expression.expression.type='ObjectExpression'])[typeAnnotation.typeName.name=/^(User|UserSchema|Collection|CollectionSchema|SaveSchema|StateSchema|AuditEventSchema)$/]",
  message:
    "Build users, collections, saves, states and audit events with their fixtures (userFixture, collectionFixture, saveFixture, stateFixture, makeAuditEvent) instead of casting an object literal.",
};

const appConfigs = await withVueTs(
  eslint.configs.recommended,
  vueTsConfigs.recommended,
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
      "e2e/.output/**",
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
  {
    files: [
      "src/v2/utils/gmeAudioWorklet.js",
      "src/v2/utils/pico8AudioWorklet.js",
    ],
    languageOptions: { globals: globals.audioWorklet },
  },
  // Import cycles. The resolver has to be the one that reads tsconfig `paths`,
  // or `@/*` and `@v2/*` go unresolved and the rule silently passes.
  {
    files: ["src/**/*.ts", "src/**/*.vue"],
    settings: {
      "import-x/resolver-next": [
        createTypeScriptImportResolver({
          project: "./tsconfig.app.json",
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
  // The md-editor config (raw HTML, XSS filter) runs from the module the bare
  // `md-editor-v3` alias points at; a deep import would skip it.
  {
    files: ["src/**/*.ts", "src/**/*.vue"],
    ignores: ["src/plugins/mdeditor.ts", "src/plugins/mdeditor-dist.d.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              // Any subpath except a stylesheet.
              regex: "^md-editor-v3/(?!.*\\.css$)",
              message:
                "Import from md-editor-v3 so the config in src/plugins/mdeditor.ts applies.",
            },
          ],
        },
      ],
    },
  },
  {
    // Frozen v1: two cycles between the console theme helpers predate the
    // rule and cannot be refactored under the freeze.
    files: ["src/console/**"],
    rules: { "import-x/no-cycle": "off" },
  },
  {
    files: ["src/**/*.ts", "src/**/*.vue"],
    ignores: [
      "src/views/**",
      "src/components/**",
      "src/console/**",
      "src/layouts/**",
      // The lazy-loaded md-editor modules, the editor's global config, and the
      // view that reaches md-editor only through an async chunk.
      "src/plugins/mdeditor*.ts",
      "src/v2/components/shared/markdown*.ts",
      "src/v2/components/GameDetails/MarkdownViewer.vue",
    ],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        { patterns: heavyImports },
      ],
    },
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
          // Rule options replace, not merge, across blocks, so repeat the heavy list.
          patterns: heavyImports,
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
      "romm/no-color-literal": "error",
      "romm/no-layout-media-query": "error",
      "romm/no-safe-area-env": "error",
    },
  },
  // Stored preferences follow the signed-in user; frozen v1 keeps its keys.
  {
    files: ["src/**/*.ts", "src/**/*.vue"],
    ignores: [
      "src/views/**",
      "src/components/**",
      "src/console/**",
      "src/layouts/**",
      "**/*.stories.ts",
      "**/*.test.ts",
      "src/composables/useUserLocalStorage.ts",
    ],
    plugins: { romm },
    rules: { "romm/no-unscoped-local-storage": "error" },
  },
  {
    files: ["src/v2/**/*.ts", "src/v2/**/*.vue"],
    ignores: ["**/*.stories.ts", "**/*.test.ts", "src/v2/utils/autofocus.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.property.name='focus']",
          message:
            "Focus through focusFromInput from @/v2/utils/autofocus, so keyboard and gamepad moves show the focus ring.",
        },
        {
          selector:
            "CallExpression[callee.object.name='emitter'][callee.property.name='on']",
          message:
            "Subscribe with useEmitterEvent from @/v2/composables/useEmitterEvent, which unsubscribes when the component unmounts.",
        },
      ],
    },
  },
  {
    files: ["src/**/*.test.ts"],
    ignores: [
      "src/views/**",
      "src/components/**",
      "src/console/**",
      "src/layouts/**",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        romCastRule,
        platformCastRule,
        modelCastRule,
      ],
    },
  },
  {
    files: ["src/v2/**/*.stories.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        romCastRule,
        platformCastRule,
        modelCastRule,
      ],
    },
  },
);

export default [
  ...appConfigs,
  // After the base configs, so its exceptions win. Outside withVueTs, whose
  // type-aware rule detection would turn on typed linting for the whole app.
  ...e2eConfig,
  // Keep last: Prettier owns formatting, so this switches off every
  // stylistic rule the two tools would otherwise fight over.
  prettierConfig,
];
