import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import type { Collection } from "@/stores/collections";
import type { User } from "@/stores/users";
import CollectionSettingsTab from "./CollectionSettingsTab.vue";

const { snackbarError } = vi.hoisted(() => ({ snackbarError: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en_US" } }),
}));
vi.mock("@/services/api/collection", () => ({
  default: { updateCollection: vi.fn(), updateSmartCollection: vi.fn() },
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: snackbarError }),
}));
vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({ toWebp: (url: string) => url }),
}));

const stored = {
  id: 8,
  name: "Favorites",
  description: "",
  user_id: 1,
  is_public: false,
  rom_ids: [1, 2],
} as unknown as Collection;

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
    } as unknown as User);
  });

  it("saves as soon as it is switched, keeping a name draft out", async () => {
    vi.mocked(collectionApi.updateCollection).mockResolvedValue({
      data: { ...stored, is_public: true },
    } as never);
    const wrapper = mountTab();

    await wrapper.get(".field").setValue("Draft name");
    await wrapper.get(".visibility").trigger("click");
    await flushPromises();

    expect(collectionApi.updateCollection).toHaveBeenCalledTimes(1);
    const { collection } = vi.mocked(collectionApi.updateCollection).mock
      .calls[0][0];
    expect(collection.is_public).toBe(true);
    expect(collection.name).toBe("Favorites");
    expect(wrapper.get(".visibility").attributes("data-on")).toBe("true");
  });

  it("flips back when the save fails", async () => {
    vi.mocked(collectionApi.updateCollection).mockRejectedValue(
      new Error("boom"),
    );
    const wrapper = mountTab();

    await wrapper.get(".visibility").trigger("click");
    await flushPromises();

    expect(wrapper.get(".visibility").attributes("data-on")).toBe("false");
    expect(snackbarError).toHaveBeenCalledTimes(1);
  });
});
