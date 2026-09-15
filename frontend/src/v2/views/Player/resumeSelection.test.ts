import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import {
  defaultResumeSelection,
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

  it("arms the newest state and binds the only save as write-back target", () => {
    const selection = defaultResumeSelection([save(1)], [state(9), state(8)]);

    expect(selection).toEqual({ save: save(1), state: state(9) });
  });

  it("leaves the save unbound when a state is armed and several saves exist", () => {
    const selection = defaultResumeSelection([save(1), save(2)], [state(9)]);

    expect(selection).toEqual({ save: null, state: state(9) });
  });
});

describe("pickSave", () => {
  it("disarms the state so the picked save is what boots", () => {
    expect(pickSave(save(2))).toEqual({ save: save(2), state: null });
  });
});

describe("pickState", () => {
  it("boots from the state and keeps the bound save for write-back", () => {
    expect(pickState(pickSave(save(2)), state(9))).toEqual({
      save: save(2),
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
      save(3, "Autosave"),
      save(4, "main_quest"),
      save(5, "speedrun"),
    ];

    expect(slotOptions(saves)).toEqual(["autosave", "main_quest", "speedrun"]);
  });
});
