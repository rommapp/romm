import { describe, expect, it } from "vitest";
import {
  NEW_SLOT_CHOICE,
  chosenSlot,
  existingSlot,
  isSlotChoice,
  preferredSlot,
  slotChoiceKey,
  slotChoices,
  slotForSave,
} from "./saveSlots";

const save = (id: number, slot: string | null = null) => ({ id, slot });

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
      NEW_SLOT_CHOICE,
      existingSlot("autosave"),
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
      NEW_SLOT_CHOICE,
      existingSlot("autosave"),
      existingSlot("main_quest"),
      existingSlot("speedrun"),
    ]);
  });

  it("matches slot names exactly, like the backend", () => {
    expect(slotChoices([save(1, "Autosave")])).toEqual([
      NEW_SLOT_CHOICE,
      existingSlot("autosave"),
      existingSlot("Autosave"),
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

describe("slotForSave", () => {
  it("follows a slotted save and keeps the choice for an archive", () => {
    expect(slotForSave(save(1, "main"), existingSlot("autosave"))).toEqual(
      existingSlot("main"),
    );
    expect(slotForSave(save(2), NEW_SLOT_CHOICE)).toBe(NEW_SLOT_CHOICE);
  });
});
