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

// HowLongToBeat stores seconds; the column and the filter both talk in hours.
const SECONDS_PER_HOUR = 3600;

// Constructing an Intl formatter is not free and the length column renders one
// per visible row, so keep one per locale.
const hourFormatters = new Map<string, Intl.NumberFormat>();

function hourFormatter(
  locale: string | undefined,
  maximumFractionDigits: number,
): Intl.NumberFormat {
  const key = `${locale ?? ""}:${maximumFractionDigits}`;
  let formatter = hourFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(locale, { maximumFractionDigits });
    hourFormatters.set(key, formatter);
  }
  return formatter;
}

/** A HowLongToBeat duration as hours rounded to the nearest half ("12.5h"),
 * or minutes under an hour. Null when unset. The rounding suits an estimate
 * read at a glance; a value the user typed wants `formatPlaytimeBound`. */
export function formatPlaytime(
  seconds: number | null | undefined,
  locale?: string,
): string | null {
  if (!seconds || seconds <= 0) return null;
  const hours = seconds / SECONDS_PER_HOUR;
  if (hours < 1) {
    const minutes = Math.round(seconds / 60);
    return minutes > 0 ? `${minutes}m` : null;
  }
  return `${hourFormatter(locale, 1).format(Math.round(hours * 2) / 2)}h`;
}

/** A stored length-filter bound as the hours it was saved with ("5.25h").
 * Reports a criterion rather than an estimate, so unlike `formatPlaytime` it
 * neither snaps to the half hour nor drops a zero (still an active filter). */
export function formatPlaytimeBound(seconds: number, locale?: string): string {
  return `${hourFormatter(locale, 2).format(seconds / SECONDS_PER_HOUR)}h`;
}

/** A length-filter bound entered in hours, as the seconds the API takes. */
export function playtimeHoursToSeconds(hours: number | null): number | null {
  if (hours == null || !Number.isFinite(hours) || hours < 0) return null;
  return Math.round(hours * SECONDS_PER_HOUR);
}

// Several providers report a year-only release as 1 January, so on that date
// the day carries no information at all.
const AMBIGUOUS_RELEASE_DAY = "1-1";

/** The `releasedDays` / `releasedBeforeYear` filter an anniversary day needs. */
export interface AnniversaryQuery {
  days: string[];
  beforeYear: number;
}

/** Which release days count as an anniversary of `today`, or null on 1 January.
 *
 *  Adds 29 February on 28 February of a non-leap year, so a leap baby surfaces
 *  once a year rather than once every four.
 */
export function anniversaryQuery(today: Date): AnniversaryQuery | null {
  const month = today.getMonth() + 1;
  const day = today.getDate();
  const year = today.getFullYear();

  const days = [`${month}-${day}`];
  if (days[0] === AMBIGUOUS_RELEASE_DAY) return null;

  const isLeapYear = new Date(year, 1, 29).getMonth() === 1;
  if (month === 2 && day === 28 && !isLeapYear) days.push("2-29");

  // Excluding the current year keeps a game released earlier today from being
  // its own anniversary.
  return { days, beforeYear: year };
}
