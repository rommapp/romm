// ESLint rules for the Playwright suite. Every e2e rule, and every exception to
// a base rule that tests legitimately break, lives here with a one-line reason.
import playwright from "eslint-plugin-playwright";
import globals from "globals";

const E2E_FILES = ["e2e/**/*.ts", "playwright.config.ts"];
const TEST_FILES = ["e2e/**/*.ts"];

// The files that build the environment the tests receive as `e2eEnv`.
const ENV_BUILDERS = ["e2e/support/e2e-environment.ts", "e2e/support/test.ts"];

/** @type {import("eslint").Linter.Config[]} */
export default [
  {
    // Reports, traces and saved sessions, all written under e2e/.output/.
    name: "e2e/output",
    ignores: ["e2e/.output/**"],
  },
  {
    name: "e2e/runtime",
    files: E2E_FILES,
    languageOptions: {
      // Specs and config run in Node, not the browser.
      globals: { ...globals.node },
    },
  },
  {
    name: "e2e/type-info",
    files: TEST_FILES,
    languageOptions: {
      // Resolves to e2e/tsconfig.json, so the app's lint stays untyped.
      parserOptions: { projectService: true },
    },
  },

  // Rules that only make sense for tests.
  {
    // Missing awaits, focused/skipped tests, page.pause(), fixed sleeps,
    // non-retrying assertions, and the rest of the plugin's recommended set.
    name: "e2e/playwright",
    ...playwright.configs["flat/recommended"],
    files: TEST_FILES,
  },
  {
    name: "e2e/playwright-options",
    files: TEST_FILES,
    rules: {
      // A conditional skip fits a test to the data a site has; an
      // unconditional one is still flagged.
      "playwright/no-skipped-test": ["warn", { allowConditional: true }],
      // An `expectSomething()` helper asserts on the test's behalf.
      "playwright/expect-expect": [
        "warn",
        { assertFunctionPatterns: ["^expect[A-Z]"] },
      ],
    },
  },
  {
    name: "e2e/rules",
    files: TEST_FILES,
    rules: {
      // An un-awaited expect() or action lets a test pass without checking.
      "@typescript-eslint/no-floating-promises": "error",
    },
  },
  {
    name: "e2e/no-api",
    files: TEST_FILES,
    rules: {
      // Tests act through the UI and observe the app's own traffic.
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='fetch']",
          message:
            "Tests don't call the API: drive the UI, and observe the app's traffic with page.waitForResponse().",
        },
        {
          // page.request and context.request send requests; response.request()
          // only reads one the app made, which is fine.
          selector:
            "MemberExpression[object.name=/^(page|context)$/][property.name='request'], ObjectPattern > Property[key.name='request']",
          message:
            "Tests don't call the API: drive the UI, and observe the app's traffic with page.waitForResponse().",
        },
      ],
    },
  },
  {
    name: "e2e/imports",
    files: TEST_FILES,
    ignores: [...ENV_BUILDERS],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          // The stock `test` has neither the app-error guard nor `e2eEnv`.
          paths: [
            {
              name: "@playwright/test",
              importNames: ["test", "expect"],
              allowTypeImports: true,
              message:
                "Import `test` and `expect` from e2e/support/test.ts, so the app-error guard and `e2eEnv` apply.",
            },
          ],
          // Tests take the environment from the `e2eEnv` fixture, so the
          // dependency shows in their signature.
          patterns: [
            {
              regex: "(^|/)e2e-environment(\\.ts)?$",
              allowTypeImports: true,
              message:
                "Take `e2eEnv` from the test arguments (`async ({ page, e2eEnv }) => ...`). Type-only imports are fine.",
            },
          ],
        },
      ],
    },
  },

  // Exceptions: rules that tests (or parts of the suite) legitimately break.
  {
    name: "e2e/exceptions/fixtures",
    files: TEST_FILES,
    rules: {
      // Playwright fixtures must destructure their first argument, even empty.
      "no-empty-pattern": "off",
    },
  },
];
