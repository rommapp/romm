// Whether RSelect's in-panel search field should autofocus when the dropdown
// opens. Desktop users want type-to-filter immediately; touch-primary devices
// must NOT autofocus, because focusing the input pops the on-screen keyboard
// before the user has chosen to type.
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
