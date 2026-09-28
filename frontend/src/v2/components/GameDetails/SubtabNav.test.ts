import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import SubtabNav, { type SubtabNavItem } from "./SubtabNav.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RMenu = {
  props: { searchable: { type: Boolean, default: false } },
  emits: ["update:search", "update:modelValue"],
  template: `<div class="menu" :data-searchable="searchable"><slot name="activator" :props="{}" /><slot /></div>`,
};
const RMenuItem = {
  props: { label: { type: String, default: "" } },
  emits: ["click"],
  template: `<button class="option" @click="$emit('click')">{{ label }}<slot name="append" /></button>`,
};

const stubs = {
  RBtn: { template: `<button class="trigger"><slot /></button>` },
  RDivider: true,
  RIcon: true,
  RMenu,
  RMenuItem,
};

function nav(items: SubtabNavItem[], props: Record<string, unknown> = {}) {
  return mount(SubtabNav, {
    props: { modelValue: items[0].id, items, ...props },
    global: { stubs },
  });
}

describe("SubtabNav", () => {
  it("heads each menu group once and hides a zero badge", () => {
    const wrapper = nav(
      [
        { id: "a", label: "Alpha", group: "Mine", badge: 0 },
        { id: "b", label: "Beta", group: "Mine", badge: 3 },
        { id: "c", label: "Gamma", group: "Community" },
      ],
      { variant: "menu" },
    );

    expect(
      wrapper.findAll(".r-v2-subtab-nav__group").map((g) => g.text()),
    ).toEqual(["Mine", "Community"]);
    expect(
      wrapper.findAll(".r-v2-subtab-nav__badge").map((b) => b.text()),
    ).toEqual(["3"]);
  });

  it("emits only when a different subtab is picked", async () => {
    const wrapper = nav([
      { id: "a", label: "Alpha" },
      { id: "b", label: "Beta" },
    ]);
    const buttons = wrapper.findAll(".r-v2-subtab-nav__btn");

    await buttons[0].trigger("click");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    await buttons[1].trigger("click");
    expect(wrapper.emitted("update:modelValue")).toEqual([["b"]]);
  });

  it("offers a filter past eight entries and matches labels loosely", async () => {
    const items = Array.from({ length: 9 }, (_, i) => ({
      id: `n${i}`,
      label: i === 4 ? "Speedrun Route" : `Note ${i}`,
    }));
    const wrapper = nav(items, { variant: "menu" });
    const menu = wrapper.findComponent(RMenu);

    expect(menu.attributes("data-searchable")).toBe("true");
    menu.vm.$emit("update:search", "  ROUTE ");
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll(".option").map((o) => o.text())).toEqual([
      "Speedrun Route",
    ]);
  });
});
