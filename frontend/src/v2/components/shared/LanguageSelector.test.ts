import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import i18n, { loadLocale } from "@/locales";
import LanguageSelector from "./LanguageSelector.vue";

type Item = { value: string; title: string };

const RSelect = {
  props: {
    modelValue: { type: String, default: "" },
    items: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue"],
  template: `<div />`,
};

async function mountSelector() {
  await loadLocale("en_US");
  const wrapper = mount(LanguageSelector, {
    global: { plugins: [i18n], stubs: { RSelect, RIcon: true } },
  });
  return { wrapper, select: wrapper.getComponent(RSelect) };
}

describe("LanguageSelector", () => {
  beforeEach(() => localStorage.clear());

  it("offers Auto first, labelled with the detected language", async () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["fr-FR"]);
    const { select } = await mountSelector();

    const items = select.props("items") as Item[];
    expect(items[0]).toEqual({ value: "auto", title: "Auto (Français)" });
    expect(select.props("modelValue")).toBe("auto");
  });

  it("stores a picked language, and clears it for Auto", async () => {
    const { select } = await mountSelector();

    select.vm.$emit("update:modelValue", "de_DE");
    await nextTick();
    expect(localStorage.getItem("settings.locale")).toBe("de_DE");
    expect(select.props("modelValue")).toBe("de_DE");

    select.vm.$emit("update:modelValue", "auto");
    await nextTick();
    expect(localStorage.getItem("settings.locale")).toBe("");
    expect(select.props("modelValue")).toBe("auto");
  });
});
