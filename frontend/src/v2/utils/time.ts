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
