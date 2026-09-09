// Not Intl.DurationFormat: its digital style always pads minutes to two
// digits ("02:37"), and player timestamps read as "2:37".

/** Seconds as a digital track position: "2:37", "0:05", "90:12". */
export function formatTrackTime(s: number | undefined | null): string {
  if (s == null || !Number.isFinite(s) || s < 0) return "0:00";
  const minutes = Math.floor(s / 60);
  const seconds = Math.floor(s % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

// Release dates are stored as UTC-midnight timestamps, so they are read back
// in UTC: local formatting shows the previous day west of Greenwich.

// Coerce before testing for emptiness, so "0" and 0 are both unset. The epoch
// itself is not a real release date -- the roms_metadata view drops it too.
function toReleaseDate(
  timestamp: number | string | null | undefined,
): Date | null {
  const ms = Number(timestamp);
  return ms ? new Date(ms) : null;
}

/** A `first_release_date` timestamp as a short date, or null if unset. */
export function formatReleaseDate(
  timestamp: number | string | null | undefined,
  locale: string,
): string | null {
  return (
    toReleaseDate(timestamp)?.toLocaleDateString(locale, {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }) ?? null
  );
}

/** The year of a `first_release_date` timestamp, or null if unset. */
export function releaseYear(
  timestamp: number | string | null | undefined,
): number | null {
  return toReleaseDate(timestamp)?.getUTCFullYear() ?? null;
}

// Where providers park year-only metadata: ScreenScraper parses a bare year
// with "%Y", CSDb publishes nothing else, and IGDB reports year precision as
// 1 January. On a 96k-rom library 28% of everything dated sits there, so the
// date carries no information and the widget skips it.
const AMBIGUOUS_RELEASE_DAY = "1-1";

/** What `releasedDays` / `releasedBeforeYear` an anniversary of `today` needs.
 *
 *  Null on 1 January, which says nothing about a release date.
 *
 *  Returns:
 *    The day itself, plus 29 February when `today` is 28 February of a
 *    non-leap year, so a leap baby surfaces once a year rather than once every
 *    four. `beforeYear` is `today`'s own year, so a game released earlier this
 *    year is not an anniversary of itself.
 */
export function anniversaryQuery(
  today: Date,
): { days: string[]; beforeYear: number } | null {
  const month = today.getMonth() + 1;
  const day = today.getDate();
  const year = today.getFullYear();

  const days = [`${month}-${day}`];
  if (days[0] === AMBIGUOUS_RELEASE_DAY) return null;

  const isLeapYear = new Date(year, 1, 29).getMonth() === 1;
  if (month === 2 && day === 28 && !isLeapYear) days.push("2-29");

  return { days, beforeYear: year };
}
