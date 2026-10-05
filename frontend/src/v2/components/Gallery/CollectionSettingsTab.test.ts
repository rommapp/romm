import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import { collectionFixture } from "@/utils/collection.fixtures";
import { userFixture } from "@/utils/user.fixtures";
import CollectionSettingsTab from "./CollectionSettingsTab.vue";

const { snackbarError } = vi.hoisted(() => ({ snackbarError: vi.fn() }));

vi.mock("vue-i18n");
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
    storeAuth().setCurrentUser(
      userFixture({ id: 1, oauth_scopes: ["collections.write"] }),
    );
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

describe("CollectionSettingsTab cover preview", () => {
  let urls = 0;

  beforeEach(() => {
    urls = 0;
    vi.spyOn(URL, "createObjectURL").mockImplementation(() => `blob:${++urls}`);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    storeAuth().setCurrentUser(
      userFixture({ id: 1, oauth_scopes: ["collections.write"] }),
    );
  });

  async function pick(wrapper: ReturnType<typeof mountTab>, file: File) {
    const input = wrapper.get<HTMLInputElement>("input[type='file']");
    Object.defineProperty(input.element, "files", {
      value: [file],
      configurable: true,
    });
    await input.trigger("change");
  }

  it("previews a picked file and revokes it when the cover is removed", async () => {
    const wrapper = mountTab();

    await pick(wrapper, new File(["a"], "a.png"));
    expect(wrapper.get("img").attributes("src")).toBe("blob:1");

    const [, , remove] = wrapper.findAll(
      ".r-v2-coll-set__cover-actions button",
    );
    await remove!.trigger("click");

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
    expect(wrapper.find("img").exists()).toBe(false);
  });

  it("revokes the preview on unmount", async () => {
    const wrapper = mountTab();
    await pick(wrapper, new File(["a"], "a.png"));

    wrapper.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });
});
