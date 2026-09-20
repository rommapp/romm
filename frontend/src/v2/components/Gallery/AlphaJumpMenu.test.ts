/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import AlphaJumpMenu from "./AlphaJumpMenu.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useWrapGridNav", () => ({
  useWrapGridNav: vi.fn(),
}));

// Renders the panel inline while open, and toggles it from the activator.
let initialFocus: readonly string[] | undefined;
const RMenuStub = defineComponent({
  props: {
    modelValue: { type: Boolean, default: false },
    initialFocus: { type: Array, default: undefined },
  },
  emits: ["update:modelValue"],
  setup(props, { slots, emit }) {
    initialFocus = props.initialFocus as readonly string[] | undefined;
    const toggle = () => emit("update:modelValue", !props.modelValue);
    return () =>
      h("div", [
        slots.activator?.({ props: { onClick: toggle } }),
        props.modelValue ? slots.default?.() : null,
      ]);
  },
});

const RBtnStub = defineComponent({
  setup(_, { slots }) {
    return () => h("button", { class: "jump-btn" }, slots.default?.());
  },
});

function mountMenu() {
  return mount(AlphaJumpMenu, {
    attachTo: document.body,
    props: {
      available: new Set(["A", "M", "Z"]),
      current: "M",
      direction: "asc",
    },
    global: { stubs: { RMenu: RMenuStub, RBtn: RBtnStub } },
  });
}

function letter(wrapper: ReturnType<typeof mountMenu>, l: string) {
  return wrapper.get(`[data-letter="${l}"]`);
}

describe("AlphaJumpMenu", () => {
  it("emits the picked letter", async () => {
    const wrapper = mountMenu();
    await wrapper.get(".jump-btn").trigger("click");

    await letter(wrapper, "Z").trigger("click");

    expect(wrapper.emitted("pick")).toEqual([["Z"]]);
    wrapper.unmount();
  });

  it("ignores letters with no games", async () => {
    const wrapper = mountMenu();
    await wrapper.get(".jump-btn").trigger("click");

    await letter(wrapper, "B").trigger("click");

    expect(wrapper.emitted("pick")).toBeUndefined();
    wrapper.unmount();
  });

  // RMenu does the focusing (and tests that); this pins the order asked for,
  // so a keyboard or pad lands on the current letter, not the first one.
  it("asks the menu to open on the current letter", () => {
    const wrapper = mountMenu();

    expect(initialFocus?.[0]).toContain("--current");
    expect(initialFocus?.[1]).toBe(".alpha-strip__btn:not(:disabled)");
    wrapper.unmount();
  });
});
