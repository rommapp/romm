import { describe, expect, it } from "vitest";
import { effectScope } from "vue";
import { useCssLength } from "./index";

function probes(): HTMLElement[] {
  return [
    ...document.body.querySelectorAll<HTMLElement>("div[aria-hidden]"),
  ].filter((el) => el.style.height === "var(--r-nav-h)");
}

describe("useCssLength", () => {
  it("sizes a probe by the expression and removes it on dispose", () => {
    const scope = effectScope();
    try {
      const length = scope.run(() => useCssLength("var(--r-nav-h)"));
      expect(probes()).toHaveLength(1);
      expect(length?.value).toBe(0);
    } finally {
      scope.stop();
    }
    expect(probes()).toHaveLength(0);
  });
});
