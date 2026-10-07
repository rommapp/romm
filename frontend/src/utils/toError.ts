/** Passes Errors through untouched (axios callers read `.response`) and wraps anything else. */
export function toError(value: unknown): Error {
  return value instanceof Error ? value : new Error(String(value));
}
