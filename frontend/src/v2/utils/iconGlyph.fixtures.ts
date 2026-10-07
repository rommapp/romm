import { vi } from "vitest";

/** Makes `getComputedStyle` report `content` for every pseudo-element. */
export function mockPseudoContent(content: string) {
  const style = document.createElement("i").style;
  style.setProperty("content", content);
  return vi.spyOn(globalThis, "getComputedStyle").mockReturnValue(style);
}
