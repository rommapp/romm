import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import ViewportShell from "./ViewportShell.vue";

describe("ViewportShell", () => {
  afterEach(() => {
    document.body.style.overflow = "";
  });

  it("locks the document scroll while mounted and restores it after", () => {
    document.body.style.overflow = "clip";
    const wrapper = mount(ViewportShell, {
      slots: { default: '<div class="content" />' },
    });

    expect(document.body.style.overflow).toBe("hidden");
    expect(wrapper.find(".content").exists()).toBe(true);

    wrapper.unmount();
    expect(document.body.style.overflow).toBe("clip");
  });

  it("clears the published scrollbar width on unmount", () => {
    document.documentElement.style.setProperty("--r-shell-scrollbar-w", "15px");
    const wrapper = mount(ViewportShell);

    wrapper.unmount();
    expect(
      document.documentElement.style.getPropertyValue("--r-shell-scrollbar-w"),
    ).toBe("");
  });
});
