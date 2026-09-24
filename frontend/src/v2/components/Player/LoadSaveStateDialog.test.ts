import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { saveFixture, stateFixture } from "@/utils/assets.fixtures";
import LoadSaveStateDialog from "./LoadSaveStateDialog.vue";

const { confirm } = vi.hoisted(() => ({
  confirm: vi.fn(async (_opts: { title: string }) => true),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirm,
}));

const RDialog = {
  props: ["modelValue"],
  template: `<div v-if="modelValue"><slot name="toolbar" /><slot name="content" /></div>`,
};
const RSliderBtnGroup = {
  props: ["modelValue", "items"],
  emits: ["update:modelValue"],
  template: `<div><button v-for="i in items" :key="i.id" :class="'tab-' + i.id" @click="$emit('update:modelValue', i.id)" /></div>`,
};
const AssetList = {
  props: { assets: { type: Array, default: () => [] } },
  emits: ["select"],
  template: `<button class="pick-save" @click="$emit('select', assets[0])" />`,
};
const AssetStrip = {
  props: { assets: { type: Array, default: () => [] } },
  emits: ["select"],
  template: `<button class="pick-state" @click="$emit('select', assets[0])" />`,
};

function makeSave(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return saveFixture({
    id: 1,
    file_name: "1.srm",
    slot: "autosave",
    ...overrides,
  });
}

function makeState(overrides: Partial<StateSchema> = {}): StateSchema {
  return stateFixture({
    id: 2,
    file_name: "2.state",
    emulator: "mgba",
    ...overrides,
  });
}

function makeRom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 3,
    user_saves: [makeSave()],
    user_states: [makeState()],
    ...overrides,
  } as DetailedRom;
}

function openDialog() {
  const emitter: Emitter<Events> = mitt<Events>();
  const saveSelected = vi.fn();
  const stateSelected = vi.fn();
  emitter.on("saveSelected", saveSelected);
  emitter.on("stateSelected", stateSelected);
  const wrapper = mount(LoadSaveStateDialog, {
    global: {
      provide: { emitter },
      stubs: { RDialog, RSliderBtnGroup, AssetList, AssetStrip, RBtn: true },
    },
  });
  const open = async () => {
    emitter.emit("selectStateDialog", makeRom());
    await flushPromises();
  };
  return { wrapper, open, saveSelected, stateSelected };
}

describe("LoadSaveStateDialog", () => {
  beforeEach(() => {
    confirm.mockClear();
  });

  it("opens on States and loads a state once confirmed", async () => {
    const { wrapper, open, stateSelected, saveSelected } = openDialog();
    await open();

    await wrapper.find(".pick-state").trigger("click");
    await flushPromises();

    expect(confirm.mock.calls[0][0].title).toBe(
      "play.load-state-confirm-title",
    );
    expect(stateSelected).toHaveBeenCalledWith(makeState());
    expect(saveSelected).not.toHaveBeenCalled();
    expect(wrapper.find(".pick-state").exists()).toBe(false);
  });

  it("loads a save from the Saves tab once confirmed", async () => {
    const { wrapper, open, saveSelected, stateSelected } = openDialog();
    await open();

    await wrapper.find(".tab-save").trigger("click");
    await wrapper.find(".pick-save").trigger("click");
    await flushPromises();

    expect(confirm.mock.calls[0][0].title).toBe("play.load-save-confirm-title");
    expect(saveSelected).toHaveBeenCalledWith(makeSave());
    expect(stateSelected).not.toHaveBeenCalled();
  });

  it("stays open and loads nothing when the load is canceled", async () => {
    confirm.mockResolvedValueOnce(false);
    const { wrapper, open, stateSelected } = openDialog();
    await open();

    await wrapper.find(".pick-state").trigger("click");
    await flushPromises();

    expect(stateSelected).not.toHaveBeenCalled();
    expect(wrapper.find(".pick-state").exists()).toBe(true);
  });

  it("reopens on States after a save was loaded", async () => {
    const { wrapper, open } = openDialog();
    await open();
    await wrapper.find(".tab-save").trigger("click");
    await wrapper.find(".pick-save").trigger("click");
    await flushPromises();

    await open();

    expect(wrapper.find(".pick-state").exists()).toBe(true);
  });
});
