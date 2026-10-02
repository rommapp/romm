/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import HiddenGamesPicker from "./HiddenGamesPicker.vue";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@v2/lib", () => {
  const stub = defineComponent({ template: "<span><slot /></span>" });
  return {
    RBtn: stub,
    RIcon: stub,
    RSpinner: defineComponent({ template: '<span class="spinner" />' }),
    RTextField: defineComponent({
      props: { modelValue: { type: String, default: "" } },
      emits: ["update:modelValue"],
      template:
        '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    }),
  };
});

vi.mock("@/services/api/rom", () => ({
  default: { getRoms, getRomSimple: vi.fn() },
}));

vi.mock("@/v2/components/shared/GameCover.vue", () => ({
  default: defineComponent({ template: "<span />" }),
}));

function page(...names: string[]) {
  return {
    data: { items: names.map((name, i) => ({ id: i + 1, name })) },
  };
}

describe("HiddenGamesPicker search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getRoms.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  function mountPicker() {
    return mount(HiddenGamesPicker, { props: { modelValue: [] } });
  }

  it("searches the trimmed term once typing settles", async () => {
    getRoms.mockResolvedValue(page("Super Mario 64"));
    const wrapper = mountPicker();

    await wrapper.find("input").setValue(" mario ");
    expect(wrapper.find(".spinner").exists()).toBe(true);
    expect(getRoms).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    expect(getRoms).toHaveBeenCalledExactlyOnceWith({
      searchTerm: "mario",
      limit: 15,
    });
    expect(wrapper.find(".spinner").exists()).toBe(false);
    expect(wrapper.text()).toContain("Super Mario 64");
  });

  it("does not search again or spin for a whitespace-only edit", async () => {
    getRoms.mockResolvedValue(page("Super Mario 64"));
    const wrapper = mountPicker();
    const input = wrapper.find("input");

    await input.setValue("mario");
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    await input.setValue("mario ");
    expect(wrapper.find(".spinner").exists()).toBe(false);
    await vi.advanceTimersByTimeAsync(300);

    expect(getRoms).toHaveBeenCalledOnce();
  });

  it("keeps the newest results when an older search answers last", async () => {
    let answerMario: (value: unknown) => void = () => {};
    getRoms
      .mockReturnValueOnce(new Promise((resolve) => (answerMario = resolve)))
      .mockResolvedValueOnce(page("Zelda"));
    const wrapper = mountPicker();
    const input = wrapper.find("input");

    await input.setValue("mario");
    await vi.advanceTimersByTimeAsync(300);
    await input.setValue("zelda");
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    answerMario(page("Super Mario 64"));
    await flushPromises();

    expect(wrapper.text()).toContain("Zelda");
    expect(wrapper.text()).not.toContain("Super Mario 64");
  });

  it("drops a pending search when it unmounts", async () => {
    const wrapper = mountPicker();

    await wrapper.find("input").setValue("mario");
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(300);

    expect(getRoms).not.toHaveBeenCalled();
  });
});
