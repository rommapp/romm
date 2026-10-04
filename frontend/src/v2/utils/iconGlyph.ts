const ICON_NAME = /^mdi-[a-z0-9-]+$/;

const drawn = new Map<string, boolean>();

/** Whether the bundled icon CSS draws `name`; an icon it lacks renders blank. */
export function hasIconGlyph(name: string): boolean {
  if (!ICON_NAME.test(name)) return false;
  const cached = drawn.get(name);
  if (cached !== undefined) return cached;

  const probe = document.createElement("i");
  probe.className = `mdi ${name}`;
  probe.style.cssText = "position: absolute; visibility: hidden";
  document.body.append(probe);
  const { content } = getComputedStyle(probe, "::before");
  probe.remove();

  // An empty value means pseudo-elements cannot be read here, so keep the icon.
  const result = content !== "none" && content !== "normal";
  drawn.set(name, result);
  return result;
}
