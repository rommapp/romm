// Not Intl.DurationFormat: its digital style always pads minutes to two
// digits ("02:37"), and player timestamps read as "2:37".

/** Seconds as a digital track position: "2:37", "0:05", "90:12". */
export function formatTrackTime(s: number | undefined | null): string {
  if (s == null || !Number.isFinite(s) || s < 0) return "0:00";
  const minutes = Math.floor(s / 60);
  const seconds = Math.floor(s % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
