// Inputs that take no typing: they act on a click, like a button.
const NON_TEXT_INPUT_TYPES = new Set([
  "button",
  "checkbox",
  "color",
  "file",
  "image",
  "radio",
  "range",
  "reset",
  "submit",
]);

/** True for fields the user types into, whose keys and pad A are theirs. */
export function isEditable(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  if (el instanceof HTMLInputElement) {
    return !el.readOnly && !NON_TEXT_INPUT_TYPES.has(el.type);
  }
  if (el instanceof HTMLTextAreaElement) return !el.readOnly;
  if (el instanceof HTMLSelectElement) return true;
  return el.isContentEditable;
}
