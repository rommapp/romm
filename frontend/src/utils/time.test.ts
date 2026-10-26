import { describe, expect, it } from "vitest";
import {
  anniversaryQuery,
  formatPlaytime,
  formatPlaytimeBound,
  formatReleaseDate,
  formatTrackTime,
  releaseYear,
} from "./time";

// West of UTC on purpose: release dates are UTC-midnight timestamps, so a
// local-time reader lands on the previous day. See rommapp/romm#4321.
process.env.TZ = "America/New_York";

describe("formatTrackTime", () => {
  it("formats seconds as a digital track position", () => {
    expect(formatTrackTime(157)).toBe("2:37");
    expect(formatTrackTime(5)).toBe("0:05");
    expect(formatTrackTime(0)).toBe("0:00");
    expect(formatTrackTime(5412)).toBe("90:12");
  });

  it("treats missing or unusable values as zero", () => {
    for (const value of [undefined, null, -3, Number.NaN, Infinity]) {
      expect(formatTrackTime(value)).toBe("0:00");
    }
  });

  it("truncates fractional seconds", () => {
    expect(formatTrackTime(61.9)).toBe("1:01");
  });
});

describe("formatReleaseDate", () => {
  it("renders the stored UTC day, not the local one", () => {
    expect(formatReleaseDate(Date.UTC(2024, 2, 15), "en-US")).toBe(
      "Mar 15, 2024",
    );
  });

  it("accepts a stringified timestamp", () => {
    expect(formatReleaseDate(String(Date.UTC(1998, 10, 21)), "en-US")).toBe(
      "Nov 21, 1998",
    );
  });

  it("returns null for missing or unusable values", () => {
    for (const value of [undefined, null, 0, "0", "", "not-a-date"]) {
      expect(formatReleaseDate(value, "en-US")).toBeNull();
    }
  });
});

describe("releaseYear", () => {
  it("reads the year in UTC", () => {
    expect(releaseYear(Date.UTC(2024, 0, 1))).toBe(2024);
  });

  it("returns null for missing or unusable values", () => {
    for (const value of [undefined, null, 0, "0", "nope"]) {
      expect(releaseYear(value)).toBeNull();
    }
  });
});

const HOUR = 3600;

describe("formatPlaytime", () => {
  it("rounds a crowd-sourced estimate to the nearest half hour", () => {
    expect(formatPlaytime(12.4 * HOUR, "en-US")).toBe("12.5h");
    expect(formatPlaytime(40 * HOUR, "en-US")).toBe("40h");
  });

  it("falls back to minutes under an hour, and null when unset", () => {
    expect(formatPlaytime(45 * 60, "en-US")).toBe("45m");
    expect(formatPlaytime(0, "en-US")).toBeNull();
    expect(formatPlaytime(null, "en-US")).toBeNull();
  });

  it("formats the number in the caller's locale", () => {
    expect(formatPlaytime(12.5 * HOUR, "de-DE")).toBe("12,5h");
  });
});

describe("formatPlaytimeBound", () => {
  it("reports the bound as saved instead of rounding it", () => {
    expect(formatPlaytimeBound(5.25 * HOUR, "en-US")).toBe("5.25h");
    expect(formatPlaytime(5.25 * HOUR, "en-US")).toBe("5.5h");
  });

  it("keeps a zero bound, which is an active filter", () => {
    expect(formatPlaytimeBound(0, "en-US")).toBe("0h");
  });

  it("formats the number in the caller's locale", () => {
    expect(formatPlaytimeBound(5.25 * HOUR, "de-DE")).toBe("5,25h");
  });
});

describe("anniversaryQuery", () => {
  /** Local time, the clock the widget reads. */
  const on = (year: number, month: number, day: number) =>
    new Date(year, month - 1, day, 12);

  it("asks for the day itself, in years before the current one", () => {
    expect(anniversaryQuery(on(2026, 9, 8))).toEqual({
      days: ["9-8"],
      beforeYear: 2026,
    });
  });

  it("returns nothing on 1 January, where year-only metadata piles up", () => {
    expect(anniversaryQuery(on(2026, 1, 1))).toBeNull();
  });

  it("rolls 29 February onto 28 February in a non-leap year", () => {
    // Otherwise a leap baby surfaces once every four years.
    expect(anniversaryQuery(on(2027, 2, 28))?.days).toEqual(["2-28", "2-29"]);
  });

  it("leaves 28 February alone in a leap year", () => {
    // 29 February is tomorrow, so it gets its own day.
    expect(anniversaryQuery(on(2028, 2, 28))?.days).toEqual(["2-28"]);
    expect(anniversaryQuery(on(2028, 2, 29))?.days).toEqual(["2-29"]);
  });

  it("does not bleed across the year boundary", () => {
    expect(anniversaryQuery(on(2026, 12, 31))).toEqual({
      days: ["12-31"],
      beforeYear: 2026,
    });
  });
});
