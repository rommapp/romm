/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import GameExceptionsPicker from "./GameExceptionsPicker.vue";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("vue-i18n");

vi.mock("@v2/lib", () => {
  const stub = defineComponent({ template: "<span><slot /></span>" });
  return {
    RBtn: defineComponent({
      emits: ["click"],
      template: `<button @click="$emit('click')"><slot /></button>`,
    }),
    RIcon: stub,
    RSliderBtnGroup: defineComponent({
      props: {
        modelValue: { type: String, default: null },
        items: { type: Array, default: () => [] },
      },
      emits: ["update:modelValue"],
      template: `<span class="toggle" :data-value="modelValue">
        <button v-for="item in items" :key="item.id" @click="$emit('update:modelValue', item.id)">{{ item.label }}</button>
      </span>`,
    }),
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

describe("GameExceptionsPicker search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getRoms.mockReset();
  });

  function mountPicker() {
    return mount(GameExceptionsPicker, { props: { hidden: [], allowed: [] } });
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

describe("GameExceptionsPicker picks", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getRoms.mockReset();
  });

  // Feeds each emitted list back in, as a parent's v-model would.
  function mountControlled() {
    const wrapper = mount(GameExceptionsPicker, {
      props: {
        hidden: [] as number[],
        allowed: [] as number[],
        "onUpdate:hidden": (hidden: number[]) => wrapper.setProps({ hidden }),
        "onUpdate:allowed": (allowed: number[]) =>
          wrapper.setProps({ allowed }),
      },
    });
    return wrapper;
  }

  async function search(
    wrapper: ReturnType<typeof mountControlled>,
    term: string,
  ) {
    await wrapper.find("input").setValue(term);
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
  }

  function resultButton(
    wrapper: ReturnType<typeof mountControlled>,
    name: string,
    action: "hide" | "allow",
  ) {
    const row = wrapper
      .findAll(".r-v2-gamex__results li")
      .find((li) => li.text().includes(name));
    return row
      ?.findAll("button")
      .find((b) => b.text() === `settings.game-exception-${action}`);
  }

  it("holds each game in one list, moving it when its toggle changes", async () => {
    getRoms.mockResolvedValue(page("Mario", "Zelda"));
    const wrapper = mountControlled();
    await search(wrapper, "a");

    await resultButton(wrapper, "Mario", "hide")?.trigger("click");
    await resultButton(wrapper, "Zelda", "allow")?.trigger("click");
    expect(wrapper.props()).toMatchObject({ hidden: [1], allowed: [2] });

    const marioRow = wrapper
      .findAll(".r-v2-gamex__selected li")
      .find((li) => li.text().includes("Mario"));
    expect(marioRow?.get(".toggle").attributes("data-value")).toBe("hide");
    await marioRow
      ?.findAll(".toggle button")
      .find((b) => b.text() === "settings.game-exception-allow")
      ?.trigger("click");

    expect(wrapper.props()).toMatchObject({ hidden: [], allowed: [2, 1] });
  });

  it("drops a removed game from its list", async () => {
    getRoms.mockResolvedValue(page("Mario"));
    const wrapper = mountControlled();
    await search(wrapper, "mario");
    await resultButton(wrapper, "Mario", "allow")?.trigger("click");

    await wrapper
      .get(".r-v2-gamex__selected .r-v2-gamex__remove")
      .trigger("click");

    expect(wrapper.props()).toMatchObject({ hidden: [], allowed: [] });
  });
});
