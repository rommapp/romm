import { describe, expect, it } from "vitest";
import type { MusicTrackSchema } from "@/__generated__";
import {
  buildFreeRadioSession,
  FREE_RADIO_DURATION_SECONDS,
  trackDurationSeconds,
} from "./freeRadio";

function track(
  romId: number,
  fileId: number,
  durationSeconds: number | null,
): MusicTrackSchema {
  return {
    rom_file_id: fileId,
    rom_id: romId,
    duration_seconds: durationSeconds,
  } as MusicTrackSchema;
}

// Deterministic stand-in for Math.random so ordering assertions are stable.
function sequenceRandom(values: number[]): () => number {
  let index = 0;
  return () => values[index++ % values.length];
}

describe("trackDurationSeconds", () => {
  it("sums durations and treats a missing one as zero", () => {
    expect(
      trackDurationSeconds([
        track(1, 1, 30),
        track(1, 2, null),
        track(1, 3, 20),
      ]),
    ).toBe(50);
  });

  it("is zero for an empty list", () => {
    expect(trackDurationSeconds([])).toBe(0);
  });
});

describe("buildFreeRadioSession", () => {
  it("drops tracks with no usable duration", () => {
    const session = buildFreeRadioSession(
      [
        track(1, 1, 60),
        track(1, 2, null),
        track(1, 3, 0),
        track(1, 4, Number.NaN),
      ],
      () => 0,
    );
    expect(session.map((t) => t.rom_file_id)).toEqual([1]);
  });

  it("keeps every track when the catalog fits in the hour", () => {
    const tracks = [track(1, 1, 60), track(2, 2, 60), track(3, 3, 60)];
    const session = buildFreeRadioSession(tracks, () => 0);
    expect(session).toHaveLength(3);
    expect(trackDurationSeconds(session)).toBeLessThanOrEqual(
      FREE_RADIO_DURATION_SECONDS,
    );
  });

  it("never exceeds the session budget", () => {
    const tracks = Array.from({ length: 200 }, (_, i) => track(i % 10, i, 120));
    const session = buildFreeRadioSession(
      tracks,
      sequenceRandom([0.1, 0.7, 0.4]),
    );
    expect(trackDurationSeconds(session)).toBeLessThanOrEqual(
      FREE_RADIO_DURATION_SECONDS,
    );
    expect(session.length).toBeGreaterThan(0);
  });

  it("interleaves albums rather than playing one straight through", () => {
    const tracks = [
      track(1, 11, 60),
      track(1, 12, 60),
      track(2, 21, 60),
      track(2, 22, 60),
    ];
    const session = buildFreeRadioSession(tracks, () => 0);
    const albumOrder = session.map((t) => t.rom_id);
    // Adjacent entries alternate albums when both still have tracks left.
    expect(albumOrder[0]).not.toBe(albumOrder[1]);
  });

  it("returns nothing when no track has a duration", () => {
    expect(buildFreeRadioSession([track(1, 1, null)], () => 0)).toEqual([]);
  });
});
