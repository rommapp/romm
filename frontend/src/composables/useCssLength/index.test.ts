import { describe, expect, it } from "vitest";
import { effectScope } from "vue";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
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

  it("tracks the probe's resolved height as it changes", () => {
    const { resize } = stubResizeObserver();
    const scope = effectScope();
    try {
      const length = scope.run(() => useCssLength("var(--r-nav-h)"));
      const [probe] = probes();
      expect(probe).toBeDefined();

      resize(probe!, 0, 105);
      expect(length?.value).toBe(105);

      resize(probe!, 0, 58);
      expect(length?.value).toBe(58);
    } finally {
      scope.stop();
    }
  });
});
