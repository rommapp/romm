import type { SaveSchema } from "@/__generated__";
import i18n from "@/locales";
import { AUTOSAVE_SLOT } from "@/services/api/save";
import {
  channelLabelForSlot,
  DEFAULT_CHANNEL_LABEL,
} from "@/v2/utils/snapshots";

/** The slot of the newest slotted save, where progress should keep going. */
export function preferredSlot(
  saves: readonly Pick<SaveSchema, "slot">[],
): string {
  return saves.find((save) => save.slot)?.slot ?? AUTOSAVE_SLOT;
}

// Where the session files new saves: a slot already in use, or one the user
// names inline.
export type SlotChoice = { kind: "existing"; slot: string } | { kind: "new" };

export const NEW_SLOT_CHOICE: SlotChoice = { kind: "new" };

export function existingSlot(slot: string): SlotChoice {
  return { kind: "existing", slot };
}

export function isSlotChoice(value: unknown): value is SlotChoice {
  return (
    typeof value === "object" &&
    value !== null &&
    "kind" in value &&
    (value.kind === "existing" || value.kind === "new")
  );
}

/**
 * The entry for a new slot first, then autosave and every slot or channel in
 * use. Names that file into the default channel fold into autosave.
 */
export function slotChoices(
  saves: readonly Pick<SaveSchema, "slot">[],
  channelLabels: readonly string[] = [],
): SlotChoice[] {
  const named = new Map<string, string>();
  for (const name of [...saves.map((save) => save.slot), ...channelLabels]) {
    if (!name || channelLabelForSlot(name) === DEFAULT_CHANNEL_LABEL) continue;
    if (!named.has(name.toLowerCase())) named.set(name.toLowerCase(), name);
  }
  return [
    NEW_SLOT_CHOICE,
    ...[AUTOSAVE_SLOT, ...named.values()].map(existingSlot),
  ];
}

/** Pickers set the new-slot entry apart from the slots that already exist. */
export function isNewSlotChoice(choice: { kind: string }): boolean {
  return choice.kind === "new";
}

export function slotChoiceTitle(choice: SlotChoice): string {
  return choice.kind === "new" ? i18n.global.t("play.new-slot") : choice.slot;
}

/** Identity for select matching: no slot name can collide with the new entry. */
export function slotChoiceKey(choice: SlotChoice): string {
  return choice.kind === "new" ? "new" : `slot:${choice.slot}`;
}

/** The slot a choice resolves to; an unnamed new slot falls back to autosave. */
export function chosenSlot(choice: SlotChoice, newSlotName: string): string {
  if (choice.kind === "existing") return choice.slot;
  return newSlotName.trim() || AUTOSAVE_SLOT;
}

/** The slot name a channel goes by, with the default channel as autosave. */
export function slotNameForChannel(label: string): string {
  return channelLabelForSlot(label) === DEFAULT_CHANNEL_LABEL
    ? AUTOSAVE_SLOT
    : label;
}

/** The choice that files into a channel. */
export function slotForChannel(label: string): SlotChoice {
  return existingSlot(slotNameForChannel(label));
}

/**
 * A slotted save, or one a channel holds, fixes the write slot; an archive
 * leaves the choice as is.
 */
export function slotForSave(
  save: Pick<SaveSchema, "slot">,
  current: SlotChoice,
  channelLabel?: string | null,
): SlotChoice {
  if (save.slot) return existingSlot(save.slot);
  return channelLabel ? slotForChannel(channelLabel) : current;
}
