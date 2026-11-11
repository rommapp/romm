/** The first item for each key, in the original order. */
export function uniqueBy<T>(
  items: readonly T[],
  key: (item: T) => unknown,
): T[] {
  const seen = new Set<unknown>();
  return items.filter((item) => {
    const k = key(item);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}
