import {
  type InputModality,
  useInputModality,
} from "@/v2/composables/useInputModality";

// Whether a search field should grab focus as soon as it appears (a dropdown
// panel opening, the Search view mounting). Desktop users want type-to-filter
// immediately; touch-primary devices must NOT autofocus, because focusing the
// input pops the on-screen keyboard before the user has chosen to type.
//
// Input modality can't decide this: a tap emits an emulated `mousedown`, so the
// modality reads "mouse" by the time the panel opens. A device-capability media
// query (`hover` + `pointer: fine`) isn't fooled by the emulated event.
export function shouldAutofocusSearch(
  win: Window | undefined = typeof window === "undefined" ? undefined : window,
): boolean {
  if (!win || typeof win.matchMedia !== "function") return true;
  return win.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

function navigatesByFocus(modality: InputModality): boolean {
  return modality === "pad" || modality === "key";
}

// Whether a modality switch should pull focus onto a view's primary action:
// only pad/key navigate by focus, and only an unfocused page is up for grabs.
export function shouldClaimFocusOnModality(
  modality: InputModality,
  active: Element | null,
  body: Element | null,
): boolean {
  return navigatesByFocus(modality) && (!active || active === body);
}

// Firefox treats a scripted focus() after a click or a gamepad's synthetic key
// as mouse focus and skips :focus-visible, so key and pad moves ask for it.
export function focusFromInput(
  el: { focus(options?: FocusOptions): void } | null | undefined,
  options: FocusOptions = {},
): void {
  const ring = navigatesByFocus(useInputModality().modality.value);
  el?.focus(ring ? { ...options, focusVisible: true } : options);
}
