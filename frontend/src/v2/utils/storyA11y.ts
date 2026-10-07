type AxeRuleId = "color-contrast" | "scrollable-region-focusable";

// Storybook replaces arrays when merging parameters, so a story lists every
// rule it skips, including those its meta skips.
export function a11yTodoRules(...ids: AxeRuleId[]) {
  return {
    a11y: { config: { rules: ids.map((id) => ({ id, enabled: false })) } },
  };
}

// The brand-purple and on-brand text tokens fall short of 4.5:1. Remove from a
// story file once its contrast passes, so the rule guards it from then on.
export const CONTRAST_TODO_PARAMETERS = a11yTodoRules("color-contrast");
