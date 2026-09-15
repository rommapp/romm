import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import {
  defaultResumeSelection,
  newerSaveThanState,
  pickSave,
  pickState,
  slotOptions,
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

  it("arms the newest state and keeps the only slotted save as write target", () => {
    const selection = defaultResumeSelection(
      [save(1, "main")],
      [state(9), state(8)],
    );

    expect(selection).toEqual({ save: save(1, "main"), state: state(9) });
  });

  it("leaves a slot-less save unbound when a state is armed", () => {
    expect(defaultResumeSelection([save(1)], [state(9)])).toEqual({
      save: null,
      state: state(9),
    });
  });

  it("leaves the save unbound when a state is armed and several saves exist", () => {
    const selection = defaultResumeSelection(
      [save(1, "main"), save(2, "alt")],
      [state(9)],
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
  it("boots from the state and keeps a slotted save for write-back", () => {
    expect(pickState(pickSave(save(2, "main")), state(9))).toEqual({
      save: save(2, "main"),
      state: state(9),
    });
  });

  it("drops a slot-less save, which a state neither boots nor writes to", () => {
    expect(pickState(pickSave(save(2)), state(9))).toEqual({
      save: null,
      state: state(9),
    });
  });
});

describe("slotOptions", () => {
  it("offers autosave even when no save exists yet", () => {
    expect(slotOptions([])).toEqual(["autosave"]);
  });

  it("lists every named slot once and skips slot-less archives", () => {
    const saves = [
      save(1, "main_quest"),
      save(2, null),
      save(3, "autosave"),
      save(4, "main_quest"),
      save(5, "speedrun"),
    ];

    expect(slotOptions(saves)).toEqual(["autosave", "main_quest", "speedrun"]);
  });

  it("matches slot names exactly, like the backend", () => {
    expect(slotOptions([save(1, "Autosave")])).toEqual([
      "autosave",
      "Autosave",
    ]);
  });
});

describe("newerSaveThanState", () => {
  const at = (updated_at: string) => ({ updated_at }) as SaveSchema;
  const stateAt = (updated_at: string) => ({ updated_at }) as StateSchema;

  it("returns the newest save when it postdates the state", () => {
    const saves = [at("2026-09-01T10:00:00Z"), at("2026-09-03T10:00:00Z")];

    expect(newerSaveThanState(saves, stateAt("2026-09-02T10:00:00Z"))).toBe(
      saves[1],
    );
  });

  it("returns null when the state is the latest progress", () => {
    const saves = [at("2026-09-01T10:00:00Z")];

    expect(newerSaveThanState(saves, stateAt("2026-09-02T10:00:00Z"))).toBe(
      null,
    );
    expect(newerSaveThanState([], stateAt("2026-09-02T10:00:00Z"))).toBe(null);
  });
});
