/**
 * Helper function to handle single vs multi-value parameters for API requests
 */
export function getFilterArray(
  single: string | null | undefined,
  multi: string[] | null | undefined,
): string[] | undefined {
  const result = (() => {
    if (multi && multi.length > 0) return multi;
    if (single) return [single];
    return undefined;
  })();
  return result;
}
