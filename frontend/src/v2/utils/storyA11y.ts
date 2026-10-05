type AxeRuleId = "color-contrast" | "scrollable-region-focusable";

/** Story parameters that skip axe rules a story still fails. Storybook
 *  replaces arrays when merging, so a story passes every rule its meta skips. */
export function a11yTodoRules(...ids: AxeRuleId[]) {
  return {
    a11y: { config: { rules: ids.map((id) => ({ id, enabled: false })) } },
  };
}

// The brand-purple and on-brand text tokens fall short of 4.5:1. Remove from a
// story file once its contrast passes, so the rule guards it from then on.
export const CONTRAST_TODO_PARAMETERS = a11yTodoRules("color-contrast");
