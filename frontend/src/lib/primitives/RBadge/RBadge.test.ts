import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RBadge from "./RBadge.vue";

function badgeClasses(props: Record<string, unknown>): string[] {
  const wrapper = mount(RBadge, { props: { content: 3, ...props } });
  const classes = wrapper.get(".r-badge").classes();
  wrapper.unmount();
  return classes;
}

describe("RBadge", () => {
  it("anchors a floating badge to its corner", () => {
    expect(badgeClasses({})).toContain("r-badge--at-top-end");
  });

  it("keeps an inline badge on its line", () => {
    const classes = badgeClasses({ inline: true });

    expect(classes).toContain("r-badge--inline");
    expect(classes.some((c) => c.startsWith("r-badge--at-"))).toBe(false);
  });
});
