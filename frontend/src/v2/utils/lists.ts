// Joining a handful of already-translated names into a phrase the reader's
// language would actually use: "File, Core and Full screen", and whatever the
// equivalent is elsewhere.
//
// Here rather than in the locale files because the alternative is a key per
// combination of names, which multiplies every time a name is added and has to
// be retranslated in all 18 locales when it does.

/**
 * The names as one phrase, in the order given.
 *
 * `locale` is the app's own locale tag, which is named with an underscore
 * (`en_US`) where Intl wants a hyphen, so it is converted rather than passed
 * through. Omitting it falls back to the runtime's default locale.
 */
export function joinNames(
  names: readonly string[],
  locale?: string | null,
): string {
  if (names.length < 2) return names[0] ?? "";
  try {
    return new Intl.ListFormat(locale?.replace("_", "-") ?? undefined, {
      style: "long",
      type: "conjunction",
    }).format(names);
  } catch {
    // An unrecognised tag throws, and a phrase is not worth a render error.
    // The same names in the same order, with a plainer separator.
    return names.join(", ");
  }
}

/** Whether two id lists hold the same ids, in any order. */
export function sameIds(a: readonly number[], b: readonly number[]): boolean {
  if (a.length !== b.length) return false;
  const left = [...a].sort((x, y) => x - y);
  const right = [...b].sort((x, y) => x - y);
  return left.every((id, i) => id === right[i]);
}
