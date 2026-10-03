import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Events } from "@/types/emitter";
import { makeRom } from "@/utils/rom.fixtures";
import EditRomDialog from "./EditRomDialog.vue";

const { getRom } = vi.hoisted(() => ({ getRom: vi.fn() }));

vi.mock("vue-i18n");
vi.mock("@/services/api/rom", () => ({
  default: { getRom, updateRom: vi.fn() },
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));
vi.mock("@/v2/utils/covers", () => ({
  getMissingCoverImage: () => "missing.svg",
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /></div>`,
};
const GameCard = {
  props: { coverSrc: { type: String, default: "" } },
  template: `<div class="card" :data-cover="coverSrc" />`,
};
const RBtn = {
  props: { icon: { type: String, default: "" } },
  emits: ["click"],
  template: `<button type="button" :data-icon="icon" @click="$emit('click')" />`,
};

const rom = makeRom({ id: 3, name: "Blur", fs_name: "blur.zip" });

async function mountDialog() {
  const emitter: Emitter<Events> = mitt<Events>();
  const wrapper = mount(EditRomDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog,
        GameCard,
        RBtn,
        RTabNav: true,
        RTextField: true,
        RIcon: true,
        AdditionalDetails: true,
        MetadataIdSection: true,
        RawMetadataPanel: true,
        DangerZone: true,
      },
    },
  });
  emitter.emit("showEditRomDialog", rom);
  await flushPromises();
  return { wrapper, emitter };
}

async function pick(
  wrapper: Awaited<ReturnType<typeof mountDialog>>["wrapper"],
) {
  const input = wrapper.get<HTMLInputElement>("input[type='file']");
  Object.defineProperty(input.element, "files", {
    value: [new File(["a"], "a.png")],
    configurable: true,
  });
  await input.trigger("change");
}

describe("EditRomDialog cover preview", () => {
  let urls = 0;

  beforeEach(() => {
    urls = 0;
    getRom.mockResolvedValue({ data: rom });
    vi.spyOn(URL, "createObjectURL").mockImplementation(() => `blob:${++urls}`);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("previews the most recent cover choice", async () => {
    const { wrapper, emitter } = await mountDialog();
    const cover = () => wrapper.get(".card").attributes("data-cover");

    await pick(wrapper);
    expect(cover()).toBe("blob:1");

    emitter.emit("updateUrlCover", "https://sgdb/grid.png");
    await flushPromises();
    expect(cover()).toBe("https://sgdb/grid.png");

    await wrapper.get("[data-icon='mdi-delete']").trigger("click");
    expect(cover()).toBe("missing.svg");

    await pick(wrapper);
    expect(cover()).toBe("blob:2");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });

  it("revokes the upload preview on unmount", async () => {
    const { wrapper } = await mountDialog();
    await pick(wrapper);

    wrapper.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });
});
