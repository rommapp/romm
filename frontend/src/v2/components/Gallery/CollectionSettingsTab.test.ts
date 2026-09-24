import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import type { User } from "@/stores/users";
import { collectionFixture } from "@/utils/collection.fixtures";
import CollectionSettingsTab from "./CollectionSettingsTab.vue";

const { snackbarError } = vi.hoisted(() => ({ snackbarError: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en_US" } }),
}));
vi.mock("@/services/api/collection", () => ({
  default: {
    updateCollection: vi.fn(),
    updateSmartCollection: vi.fn(),
    setCollectionVisibility: vi.fn(),
    setSmartCollectionVisibility: vi.fn(),
  },
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: snackbarError }),
}));
vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({ toWebp: (url: string) => url }),
}));

const stored = collectionFixture({ id: 8, rom_ids: [1, 2], rom_count: 2 });

// Stands in for the switch: a click asks to flip it.
const VisibilitySwitch = {
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<button class="visibility" :data-on="modelValue" @click="$emit('update:modelValue', !modelValue)" />`,
};
const RTextField = {
  props: { modelValue: { type: String, default: "" } },
  emits: ["update:modelValue"],
  template: `<input class="field" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
};

function mountTab() {
  return mount(CollectionSettingsTab, {
    props: { kind: "regular", collection: stored },
    global: {
      stubs: {
        VisibilitySwitch,
        RTextField,
        CollectionMosaic: true,
        DangerZone: true,
        RIcon: true,
      },
    },
  });
}

describe("CollectionSettingsTab visibility", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    storeAuth().setCurrentUser({
      id: 1,
      oauth_scopes: ["collections.write"],
    } as User);
  });

  it("saves on its own route as soon as it is switched", async () => {
    vi.mocked(collectionApi.setCollectionVisibility).mockResolvedValue({
      data: { ...stored, is_public: true },
    } as never);
    const wrapper = mountTab();

    await wrapper.get(".field").setValue("Draft name");
    await wrapper.get(".visibility").trigger("click");
    await flushPromises();

    expect(collectionApi.setCollectionVisibility).toHaveBeenCalledWith({
      id: 8,
      isPublic: true,
    });
    // The name draft stays unsent, and nothing rewrites the membership.
    expect(collectionApi.updateCollection).not.toHaveBeenCalled();
    expect(wrapper.get(".visibility").attributes("data-on")).toBe("true");
  });

  it("keeps a late answer off a collection opened since", async () => {
    let answer!: (value: unknown) => void;
    vi.mocked(collectionApi.setCollectionVisibility).mockReturnValue(
      new Promise((resolve) => (answer = resolve)) as never,
    );
    const wrapper = mountTab();

    await wrapper.get(".visibility").trigger("click");
    await wrapper.setProps({
      collection: collectionFixture({ id: 9, name: "Racers" }),
    });
    answer({ data: { ...stored, is_public: true } });
    await flushPromises();

    expect(wrapper.emitted("saved")).toBeUndefined();
  });

  it("flips back when the save fails", async () => {
    vi.mocked(collectionApi.setCollectionVisibility).mockRejectedValue(
      new Error("boom"),
    );
    const wrapper = mountTab();

    await wrapper.get(".visibility").trigger("click");
    await flushPromises();

    expect(wrapper.get(".visibility").attributes("data-on")).toBe("false");
    expect(snackbarError).toHaveBeenCalledTimes(1);
  });
});
