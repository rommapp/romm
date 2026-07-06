import { composeStories } from "@storybook/vue3-vite";
import axe from "axe-core";
import { describe, expect, it } from "vitest";

type StoryModule = Record<string, unknown>;

// The addon-a11y story parameter shape we honour here. `test` mirrors
// @storybook/addon-a11y's own knob: "error" fails the test on any
// violation, "todo" surfaces them as warnings without failing (a ratchet
// escape hatch), "off" skips the scan entirely. `options` is forwarded to
// axe.run so a story can scope or disable individual rules.
type A11yParameters = {
  test?: "error" | "todo" | "off";
  options?: axe.RunOptions;
};

type ComposedStory = {
  run?: (context?: { canvasElement?: HTMLElement }) => Promise<void>;
  parameters?: { a11y?: A11yParameters };
};

// color-contrast needs real layout + computed colors, which happy-dom does
// not provide, so it is disabled in this (non-browser) runner. Contrast is
// covered by the Storybook a11y panel and, when added, a browser-mode run.
const DEFAULT_AXE_OPTIONS: axe.RunOptions = {
  rules: { "color-contrast": { enabled: false } },
};

function formatViolations(violations: axe.Result[]): string {
  return violations
    .map((v) => {
      const nodes = v.nodes
        .map((n) => `      ${n.html}\n        ${n.failureSummary ?? ""}`)
        .join("\n");
      return `  [${v.impact ?? "n/a"}] ${v.id}: ${v.help}\n${nodes}\n    ${v.helpUrl}`;
    })
    .join("\n\n");
}

async function checkA11y(
  element: HTMLElement,
  params: A11yParameters,
  storyName: string,
): Promise<void> {
  const mode = params.test ?? "error";
  if (mode === "off") return;

  const options: axe.RunOptions = {
    ...DEFAULT_AXE_OPTIONS,
    ...params.options,
    rules: { ...DEFAULT_AXE_OPTIONS.rules, ...params.options?.rules },
  };

  const results = await axe.run(element, options);
  if (results.violations.length === 0) return;

  const report = formatViolations(results.violations);
  if (mode === "todo") {
    console.warn(
      `a11y (todo) "${storyName}" has ${results.violations.length} violation(s):\n${report}`,
    );
    return;
  }

  expect(
    results.violations,
    `Accessibility violations in "${storyName}":\n${report}`,
  ).toHaveLength(0);
}

const storyModules = import.meta.glob<StoryModule>(
  "../src/v2/lib/**/*.stories.ts",
  { eager: true },
);

for (const [path, module] of Object.entries(storyModules)) {
  const composed = composeStories(module);
  describe(path.replace(/^\.\.\//, ""), () => {
    for (const [name, story] of Object.entries(composed)) {
      const s = story as ComposedStory;
      it(name, async () => {
        if (typeof s.run !== "function") {
          throw new Error(
            `Story "${name}" has no run() helper — composeStories incompatible.`,
          );
        }
        // Render into an owned canvas so axe scans exactly this story's
        // subtree, then clean it up so stories stay isolated.
        const canvasElement = document.createElement("div");
        document.body.appendChild(canvasElement);
        try {
          await s.run({ canvasElement });
          await checkA11y(
            canvasElement,
            s.parameters?.a11y ?? {},
            `${path.replace(/^\.\.\//, "")} > ${name}`,
          );
        } finally {
          canvasElement.remove();
        }
      });
    }
  });
}
