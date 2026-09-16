import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import {
  NEW_SLOT_CHOICE,
  chosenSlot,
  defaultResumeSelection,
  existingSlot,
  isSlotChoice,
  newerThanPick,
  pickSave,
  pickState,
  preferredSlot,
  slotChoiceKey,
  slotChoices,
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
  it("boots from the state and drops any picked save", () => {
    expect(pickState(state(9))).toEqual({ save: null, state: state(9) });
  });
});

describe("preferredSlot", () => {
  it("follows the newest slotted save and skips archives", () => {
    expect(preferredSlot([save(1), save(2, "main"), save(3, "alt")])).toBe(
      "main",
    );
  });

  it("falls back to autosave when nothing is slotted", () => {
    expect(preferredSlot([])).toBe("autosave");
    expect(preferredSlot([save(1)])).toBe("autosave");
  });
});

describe("slotChoices", () => {
  it("offers autosave and a new slot even when no save exists yet", () => {
    expect(slotChoices([])).toEqual([
      existingSlot("autosave"),
      NEW_SLOT_CHOICE,
    ]);
  });

  it("lists every named slot once and skips slot-less archives", () => {
    const saves = [
      save(1, "main_quest"),
      save(2, null),
      save(3, "autosave"),
      save(4, "main_quest"),
      save(5, "speedrun"),
    ];

    expect(slotChoices(saves)).toEqual([
      existingSlot("autosave"),
      existingSlot("main_quest"),
      existingSlot("speedrun"),
      NEW_SLOT_CHOICE,
    ]);
  });

  it("matches slot names exactly, like the backend", () => {
    expect(slotChoices([save(1, "Autosave")])).toEqual([
      existingSlot("autosave"),
      existingSlot("Autosave"),
      NEW_SLOT_CHOICE,
    ]);
  });
});

describe("slotChoiceKey", () => {
  it("keeps a slot literally named like the new entry apart from it", () => {
    expect(slotChoiceKey(existingSlot("new"))).not.toBe(
      slotChoiceKey(NEW_SLOT_CHOICE),
    );
  });
});

describe("chosenSlot", () => {
  it("resolves an existing slot to its name", () => {
    expect(chosenSlot(existingSlot("main_quest"), "ignored")).toBe(
      "main_quest",
    );
  });

  it("trims the typed name for a new slot and falls back to autosave", () => {
    expect(chosenSlot(NEW_SLOT_CHOICE, "  speedrun ")).toBe("speedrun");
    expect(chosenSlot(NEW_SLOT_CHOICE, "   ")).toBe("autosave");
  });
});

describe("isSlotChoice", () => {
  it("accepts both choice kinds and rejects anything else", () => {
    expect(isSlotChoice(existingSlot("main"))).toBe(true);
    expect(isSlotChoice(NEW_SLOT_CHOICE)).toBe(true);
    expect(isSlotChoice("slot:main")).toBe(false);
    expect(isSlotChoice({ kind: "other" })).toBe(false);
    expect(isSlotChoice(null)).toBe(false);
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
