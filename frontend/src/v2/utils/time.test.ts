import { describe, expect, it } from "vitest";
import { formatReleaseDate, formatTrackTime, releaseYear } from "./time";

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
