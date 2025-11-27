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
  // Only log non-empty results to reduce console noise
  if (result) {
    console.log("getFilterArray - result:", result);
  }
  return result;
}
