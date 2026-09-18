import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { SearchRom, SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import MatchRomDialog from "./MatchRomDialog.vue";

const { searchRom } = vi.hoisted(() => ({ searchRom: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ name: "gallery" }),
}));
vi.mock("@/services/api/rom", () => ({
  default: { searchRom, updateRom: vi.fn() },
}));
vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ value: { METADATA_SOURCES: { IGDB_API_ENABLED: true } } }),
}));
vi.mock("@/stores/roms", () => ({ default: () => ({ currentRom: null }) }));
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ lgAndUp: ref(true) }),
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ applyRomWrite: vi.fn() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RDialog = {
  props: ["modelValue"],
  emits: ["close"],
  template: `<div v-if="modelValue"><slot name="toolbar" /><slot name="content" /></div>`,
};
const RBtn = {
  emits: ["click"],
  template: `<button type="button" @click="$emit('click')"><slot /></button>`,
};
const MatchRomBodyGrid = {
  props: { results: { type: Array, default: () => [] } },
  template: `<ul><li v-for="r in results" :key="r.name" class="match">{{ r.name }}</li></ul>`,
};

function rom(id: number, name: string): SimpleRom {
  return {
    id,
    name,
    fs_name: `${name}.zip`,
    fs_name_no_tags: name,
    is_identified: true,
  } as SimpleRom;
}

function match(name: string): SearchRom {
  return { name, igdb_id: 1, platform_id: 1 } as SearchRom;
}

describe("MatchRomDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("drops a search left running when the dialog closes", async () => {
    let finishStale: (value: { data: SearchRom[] }) => void = () => {};
    searchRom
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finishStale = resolve;
        }),
      )
      .mockResolvedValueOnce({ data: [match("Doom")] });
    const emitter: Emitter<Events> = mitt<Events>();
    const wrapper = mount(MatchRomDialog, {
      global: {
        provide: { emitter },
        stubs: {
          RDialog,
          RBtn,
          MatchRomBodyGrid,
          RTextField: true,
          RSelect: true,
          RSliderBtnGroup: true,
          RIcon: true,
          RSpinner: true,
          RTooltip: true,
        },
      },
    });
    const search = () =>
      wrapper
        .findAll("button")
        .find((b) => b.text() === "common.search")
        ?.trigger("click");

    emitter.emit("showMatchRomDialog", rom(1, "Blur"));
    await flushPromises();
    await search();
    wrapper.findComponent(RDialog).vm.$emit("close");

    emitter.emit("showMatchRomDialog", rom(2, "Doom"));
    await flushPromises();
    await search();
    await flushPromises();
    finishStale({ data: [match("Blur")] });
    await flushPromises();

    expect(wrapper.findAll("li.match").map((li) => li.text())).toEqual([
      "Doom",
    ]);
  });
});
