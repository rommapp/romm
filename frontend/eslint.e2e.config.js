// ESLint rules for the Playwright suite, each with a one-line reason.
import playwright from "eslint-plugin-playwright";

const TEST_FILES = ["e2e/**/*.ts"];

/** @type {import("eslint").Linter.Config[]} */
export default [
  {
    // Missing awaits, focused tests, page.pause(), fixed sleeps, non-retrying
    // assertions, and the rest of the plugin's recommended set.
    name: "e2e/playwright",
    ...playwright.configs["flat/recommended"],
    files: TEST_FILES,
  },
  {
    name: "e2e/rules",
    files: TEST_FILES,
    languageOptions: {
      // Type info for no-floating-promises. Resolves to tsconfig.node.json, so
      // the app's lint stays untyped.
      parserOptions: { projectService: true },
    },
    rules: {
      // An `expectSomething()` helper asserts on the test's behalf.
      "playwright/expect-expect": [
        "warn",
        { assertFunctionPatterns: ["^expect[A-Z]"] },
      ],
      // An un-awaited helper lets a test pass without checking; the plugin's
      // own await rule only knows Playwright's calls.
      "@typescript-eslint/no-floating-promises": "error",
      // Tests act through the UI and observe the app's own traffic.
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='fetch']",
          message:
            "Tests don't call the API: drive the UI, and observe the app's traffic with page.waitForResponse().",
        },
        {
          // Any `.request` that isn't called (page.request, page.context().request)
          // sends requests; response.request() only reads one the app made.
          selector:
            "MemberExpression[property.name='request']:not(CallExpression > MemberExpression.callee), ObjectPattern > Property[key.name='request'], ImportDeclaration[source.value='@playwright/test'] > ImportSpecifier[imported.name='request']",
          message:
            "Tests don't call the API: drive the UI, and observe the app's traffic with page.waitForResponse().",
        },
      ],
    },
  },
  {
    name: "e2e/imports",
    files: TEST_FILES,
    // test.ts builds the suite's `test` from the stock one.
    ignores: ["e2e/support/test.ts"],
    rules: {
      // The stock `test` lacks the app-error guard.
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@playwright/test",
              importNames: ["test", "expect"],
              allowTypeImports: true,
              message:
                "Import `test` and `expect` from e2e/support/test.ts, so the app-error guard applies.",
            },
          ],
        },
      ],
    },
  },
];
