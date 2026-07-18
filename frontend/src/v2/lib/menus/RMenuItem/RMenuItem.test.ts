import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import RMenuItem from "./RMenuItem.vue";

// Regression guard: a `:to` item must render a real `<a href>`. RMenuItem
// previously rendered RouterLink via `<component :is="'router-link'">` while
// also blindly binding `:href="undefined"` — a fallthrough `href` attribute
// clobbers the href RouterLink computes from `to`, producing an href-less
// <a>. Such an anchor offers no "open in new tab" context menu and Ctrl/⌘-
// click silently no-ops. Keep the rendered href intact.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: "/", component: { template: "<div />" } },
    {
      path: "/profile/:user",
      name: "userProfile",
      component: { template: "<div />" },
    },
  ],
});

describe("RMenuItem link rendering", () => {
  it("renders a `to` item as an <a> with a resolved href", async () => {
    await router.push("/");
    await router.isReady();
    const wrapper = mount(RMenuItem, {
      props: { to: { name: "userProfile", params: { user: 1 } }, label: "P" },
      global: { plugins: [router] },
    });
    const a = wrapper.find("a");
    expect(a.exists()).toBe(true);
    expect(a.attributes("href")).toBe("/profile/1");
    expect(a.attributes("role")).toBe("menuitem");
  });

  it("renders an `href` item as an <a> with that href", () => {
    const wrapper = mount(RMenuItem, { props: { href: "/foo", label: "F" } });
    expect(wrapper.find("a").attributes("href")).toBe("/foo");
  });

  it("renders a plain action item as a <button>", () => {
    const wrapper = mount(RMenuItem, {
      props: { label: "Act" },
      attrs: { onClick: () => {} },
    });
    const btn = wrapper.find("button");
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("type")).toBe("button");
  });

  it("drops the href on a disabled link item (no native navigation)", () => {
    const wrapper = mount(RMenuItem, {
      props: { href: "/foo", label: "F", disabled: true },
    });
    const a = wrapper.find("a");
    expect(a.attributes("href")).toBeUndefined();
    expect(a.attributes("aria-disabled")).toBe("true");
  });
});
