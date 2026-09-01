import { describe, expect, it } from "vitest";
import { formatTrackTime } from "./time";

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
