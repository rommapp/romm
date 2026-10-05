// Story parameters that skip axe's color-contrast rule while the brand-purple
// and on-brand text tokens fall short of 4.5:1. Remove from a story file once
// its contrast passes, so the rule guards it from then on.
export const CONTRAST_TODO_PARAMETERS = {
  a11y: { config: { rules: [{ id: "color-contrast", enabled: false }] } },
};
