/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import BrowseMode from "./BrowseMode.vue";

vi.mock("vue-i18n");

vi.mock("@v2/lib", () => {
  const stub = defineComponent({ template: "<div><slot /></div>" });
  return {
    REmptyState: stub,
    RIcon: stub,
    RList: stub,
    RListItem: stub,
    RSkeletonBlock: stub,
    RTextField: defineComponent({
      props: { modelValue: { type: String, default: "" } },
      emits: ["update:modelValue"],
      template:
        '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    }),
  };
});

vi.mock("@/services/api/music", () => ({
  default: { getTracks: vi.fn() },
}));

vi.mock("@/stores/musicFavorites", () => ({
  default: () => ({ merge: vi.fn() }),
}));

vi.mock("@/v2/components/Soundtrack/Panel.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/shared/PlatformIcon.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

describe("BrowseMode search", () => {
  beforeEach(() => vi.useFakeTimers());

  function mountBrowse() {
    const loadEntries = vi.fn().mockResolvedValue([]);
    const wrapper = mount(BrowseMode, {
      props: {
        icon: "mdi-account-music",
        loadEntries,
        filterFor: () => ({}),
        selected: "",
        searchable: true,
      },
    });
    return { wrapper, loadEntries };
  }

  it("loads entries once typing settles, with the trimmed term", async () => {
    const { wrapper, loadEntries } = mountBrowse();
    expect(loadEntries).toHaveBeenCalledExactlyOnceWith("");

    const input = wrapper.find("input");
    await input.setValue("ko");
    await input.setValue(" koji ");
    expect(loadEntries).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(250);
    expect(loadEntries).toHaveBeenCalledTimes(2);
    expect(loadEntries).toHaveBeenLastCalledWith("koji");
  });

  it("skips the reload when only surrounding whitespace changed", async () => {
    const { wrapper, loadEntries } = mountBrowse();
    const input = wrapper.find("input");

    await input.setValue("koji");
    await vi.advanceTimersByTimeAsync(250);
    await input.setValue("koji ");
    await vi.advanceTimersByTimeAsync(250);

    expect(loadEntries).toHaveBeenCalledTimes(2);
  });

  it("refreshes with the typed text when a search is still pending", async () => {
    const { wrapper, loadEntries } = mountBrowse();

    await wrapper.find("input").setValue("koji");
    await wrapper.setProps({ refreshToken: 1 });
    await vi.advanceTimersByTimeAsync(250);

    expect(loadEntries.mock.calls).toEqual([[""], ["koji"]]);
  });

  it("drops a pending search when the view unmounts", async () => {
    const { wrapper, loadEntries } = mountBrowse();

    await wrapper.find("input").setValue("koji");
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(250);

    expect(loadEntries).toHaveBeenCalledTimes(1);
  });
});
