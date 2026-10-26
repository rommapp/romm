/** The whitespace HTML collapses when it renders the phrase; NBSP stays significant. */
const COLLAPSIBLE_WHITESPACE = /[ \t\n\r\f]+/g;

function normalize(value: string): string {
  return value.replace(COLLAPSIBLE_WHITESPACE, " ").replace(/^ | $/g, "");
}

/**
 * Whether `typed` matches the phrase a type-to-confirm dialog shows, compared
 * as rendered so a stored double space can be typed back. A phrase that
 * renders as nothing must match exactly, or the empty field would pass.
 */
export function typedMatches(required: string, typed: string): boolean {
  const normalizedRequired = normalize(required);
  if (!normalizedRequired) return typed === required;
  return normalize(typed) === normalizedRequired;
}
