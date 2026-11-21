import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import PageHeadBand from "./PageHeadBand.vue";

describe("PageHeadBand", () => {
  it("puts the header above the divider and keeps the caller's class on the band", () => {
    const wrapper = mount(PageHeadBand, {
      attrs: { class: "r-shell__header" },
      slots: { default: '<h1 class="title">Home</h1>' },
    });

    const children = wrapper.element.children;
    expect(wrapper.classes()).toContain("r-shell__header");
    expect(children[0]?.classList.contains("title")).toBe(true);
    expect(children[1]?.classList.contains("page-head-band__divider")).toBe(
      true,
    );
  });

  it.each(["content", "toolbar", "panes"] as const)(
    "sets the space under the divider for %s",
    (followedBy) => {
      const wrapper = mount(PageHeadBand, { props: { followedBy } });

      expect(wrapper.classes()).toContain(`page-head-band--${followedBy}`);
    },
  );

  it("defaults to plain content under the divider", () => {
    expect(mount(PageHeadBand).classes()).toContain("page-head-band--content");
  });
});
