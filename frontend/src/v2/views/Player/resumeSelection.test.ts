import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import {
  clearState,
  defaultResumeSelection,
  newerThanPick,
  pickSave,
  pickState,
} from "./resumeSelection";

const save = (id: number, slot: string | null = null) =>
  ({ id, file_name: `${id}.srm`, slot }) as SaveSchema;
const state = (id: number) => ({ id, file_name: `${id}.state` }) as StateSchema;

describe("defaultResumeSelection", () => {
  it("starts fresh when there is nothing to resume from", () => {
    expect(defaultResumeSelection([], [])).toEqual({ save: null, state: null });
  });

  it("boots from the newest save when no state is compatible", () => {
    expect(defaultResumeSelection([save(1), save(2)], [])).toEqual({
      save: save(1),
      state: null,
    });
  });

  it("arms the newest state and binds no save", () => {
    const selection = defaultResumeSelection(
      [save(1, "main"), save(2)],
      [state(9), state(8)],
    );

    expect(selection).toEqual({ save: null, state: state(9) });
  });
});

describe("pickSave", () => {
  it("disarms the state so the picked save is what boots", () => {
    expect(pickSave(save(2))).toEqual({ save: save(2), state: null });
  });
});

describe("pickState", () => {
  it("boots from the state and sets the picked save aside", () => {
    expect(pickState(pickSave(save(2)), state(9))).toEqual({
      save: null,
      state: state(9),
      aside: save(2),
    });
  });

  it("keeps the aside save across a second state pick", () => {
    const first = pickState(pickSave(save(2)), state(9));

    expect(pickState(first, state(8)).aside).toEqual(save(2));
  });
});

describe("clearState", () => {
  it("restores the save the state displaced", () => {
    expect(clearState(pickState(pickSave(save(2)), state(9)))).toEqual({
      save: save(2),
      state: null,
    });
  });

  it("leaves nothing picked when the state was the default", () => {
    expect(clearState(defaultResumeSelection([save(1)], [state(9)]))).toEqual({
      save: null,
      state: null,
    });
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

    expect(
      newerThanPick(
        saves,
        states,
        pickState({ save: null, state: null }, states[0]),
      ),
    ).toEqual({
      kind: "state",
      asset: states[1],
    });
    expect(
      newerThanPick(
        saves,
        [states[0]],
        pickState({ save: null, state: null }, states[0]),
      ),
    ).toEqual({
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
