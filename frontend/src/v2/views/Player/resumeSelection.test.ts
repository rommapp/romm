import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import {
  defaultResumeSelection,
  newerThanPick,
  pickSave,
  pickState,
} from "./resumeSelection";

const save = (id: number, updated_at = "", slot: string | null = null) =>
  ({ id, file_name: `${id}.srm`, updated_at, slot }) as SaveSchema;
const state = (id: number, updated_at = "") =>
  ({ id, file_name: `${id}.state`, updated_at }) as StateSchema;

describe("defaultResumeSelection", () => {
  it("starts fresh when there is nothing to resume from", () => {
    expect(defaultResumeSelection([], [])).toEqual({ save: null, state: null });
  });

  it("boots from the newest save when no state is compatible", () => {
    const saves = [
      save(1, "2026-09-01T10:00:00Z"),
      save(2, "2026-09-02T10:00:00Z"),
    ];

    expect(defaultResumeSelection(saves, [])).toEqual({
      save: saves[1],
      state: null,
    });
  });

  it("arms the newest state when it is the latest progress", () => {
    const saves = [
      save(1, "2026-09-03T10:00:00Z", "main"),
      save(2, "2026-09-01T10:00:00Z"),
    ];
    const states = [
      state(9, "2026-09-02T10:00:00Z"),
      state(8, "2026-09-04T10:00:00Z"),
    ];

    expect(defaultResumeSelection(saves, states)).toEqual({
      save: null,
      state: states[1],
    });
  });

  it("boots from the save when it postdates every compatible state", () => {
    const saves = [save(1, "2026-09-05T10:00:00Z", "main")];
    const states = [state(9, "2026-09-04T10:00:00Z")];

    expect(defaultResumeSelection(saves, states)).toEqual({
      save: saves[0],
      state: null,
    });
  });

  it("lets the state win a tie, since it restores the SRAM too", () => {
    const saves = [save(1, "2026-09-05T10:00:00Z")];
    const states = [state(9, "2026-09-05T10:00:00Z")];

    expect(defaultResumeSelection(saves, states)).toEqual({
      save: null,
      state: states[0],
    });
  });
});

describe("pickSave", () => {
  it("disarms the state so the picked save is what boots", () => {
    expect(pickSave(save(2))).toEqual({ save: save(2), state: null });
  });
});

describe("pickState", () => {
  it("boots from the state and drops any picked save", () => {
    expect(pickState(state(9))).toEqual({ save: null, state: state(9) });
  });
});

describe("newerThanPick", () => {
  const at = (id: number, updated_at: string) =>
    ({ id, updated_at }) as SaveSchema;
  const stateAt = (id: number, updated_at: string) =>
    ({ id, updated_at }) as StateSchema;

  it("points at the newest asset of either kind", () => {
    const saves = [at(1, "2026-09-03T10:00:00Z")];
    const states = [
      stateAt(9, "2026-09-01T10:00:00Z"),
      stateAt(8, "2026-09-05T10:00:00Z"),
    ];

    expect(newerThanPick(saves, states, pickState(states[0]))).toEqual({
      kind: "state",
      asset: states[1],
    });
    expect(newerThanPick(saves, [states[0]], pickState(states[0]))).toEqual({
      kind: "save",
      asset: saves[0],
    });
  });

  it("warns about a newer save even when a save is picked", () => {
    const saves = [
      at(1, "2026-09-01T10:00:00Z"),
      at(2, "2026-09-02T10:00:00Z"),
    ];

    expect(newerThanPick(saves, [], pickSave(saves[0]))).toEqual({
      kind: "save",
      asset: saves[1],
    });
  });

  it("stays quiet when the pick is the latest progress or nothing is picked", () => {
    const saves = [at(1, "2026-09-03T10:00:00Z")];
    const states = [stateAt(9, "2026-09-02T10:00:00Z")];

    expect(newerThanPick(saves, states, pickSave(saves[0]))).toBe(null);
    expect(newerThanPick(saves, states, { save: null, state: null })).toBe(
      null,
    );
  });
});
