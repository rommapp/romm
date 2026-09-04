import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import RefreshMetadataDialog from "./RefreshMetadataDialog.vue";

const { startScan, persistSelection, snackbarInfo, sources } = vi.hoisted(
  () => ({
    startScan: vi.fn(() => true),
    persistSelection: vi.fn(),
    snackbarInfo: vi.fn(),
    sources: { value: [] as { value: string }[] },
  }),
);

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useScanTrigger", () => ({
  useScanTrigger: () => ({ startScan }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    info: snackbarInfo,
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  }),
}));
vi.mock("@/v2/composables/useScanProviders", async () => {
  const { computed, ref } = await import("vue");
  return {
    useScanProviders: () => ({
      calculateHashes: ref(true),
      generalProviders: ref([]),
      specificProviders: ref([]),
      metadataSources: ref([]),
      effectiveMetadataSources: computed(() => sources.value),
      generalAllSelected: ref(false),
      specificAllSelected: ref(false),
      isLaunchboxSelected: ref(false),
      launchboxRemoteEnabled: ref(false),
      hashMatchers: ref([]),
      setHashMatcher: vi.fn(),
      isHashMatcherOn: () => false,
      buildScanPayload: () => ({
        apis: sources.value.map((s) => s.value),
        launchbox_remote_enabled: false,
        playmatch_enabled: false,
      }),
      persistSelection,
    }),
  };
});

const RDialog = {
  props: ["modelValue"],
  template: `<div v-if="modelValue"><slot name="header" /><slot name="content" /><slot name="footer" /></div>`,
};
const RSelect = {
  props: ["modelValue", "items"],
  emits: ["update:modelValue"],
  template: `<select class="sel" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)"><option v-for="i in items" :key="i.value" :value="i.value">{{ i.title }}</option></select>`,
};
const RBtn = {
  props: ["disabled"],
  emits: ["click"],
  template: `<button class="btn" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
};

function rom(): SimpleRom {
  return {
    id: 5,
    platform_id: 2,
    name: "Game",
    fs_name: "Game.zip",
  } as SimpleRom;
}

async function openDialog() {
  const emitter: Emitter<Events> = mitt<Events>();
  const wrapper = mount(RefreshMetadataDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog,
        RSelect,
        RBtn,
        RAvatar: true,
        RAlert: true,
        RIcon: true,
        RSwitch: true,
        RTooltip: true,
      },
    },
  });
  emitter.emit("showRefreshMetadataDialog", rom());
  await flushPromises();
  return wrapper;
}

function scanTypeSelect(wrapper: Awaited<ReturnType<typeof openDialog>>) {
  return wrapper.findAll("select.sel").at(-1)!;
}

function scanButton(wrapper: Awaited<ReturnType<typeof openDialog>>) {
  return wrapper.findAll("button.btn").at(-1)!;
}

describe("RefreshMetadataDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    startScan.mockReturnValue(true);
    sources.value = [];
  });

  it("offers the files refresh and starts it without any provider", async () => {
    const wrapper = await openDialog();
    const options = scanTypeSelect(wrapper)
      .findAll("option")
      .map((o) => o.attributes("value"));
    expect(options).toContain("quick");

    await scanTypeSelect(wrapper).setValue("quick");
    expect(scanButton(wrapper).attributes("disabled")).toBeUndefined();
    await scanButton(wrapper).trigger("click");

    expect(startScan).toHaveBeenCalledWith([
      {
        platforms: [2],
        roms_ids: [5],
        type: "quick",
        apis: [],
        launchbox_remote_enabled: false,
        playmatch_enabled: false,
      },
    ]);
    expect(persistSelection).toHaveBeenCalled();
    expect(snackbarInfo).toHaveBeenCalledWith(
      "rom.refreshing-files",
      expect.anything(),
    );
  });

  it("still needs a provider for a metadata refresh", async () => {
    const wrapper = await openDialog();

    await scanTypeSelect(wrapper).setValue("update");

    expect(scanButton(wrapper).attributes("disabled")).toBeDefined();
  });

  it("keeps the dialog open when a scan is already running", async () => {
    startScan.mockReturnValue(false);
    const wrapper = await openDialog();

    await scanTypeSelect(wrapper).setValue("quick");
    await scanButton(wrapper).trigger("click");

    expect(persistSelection).not.toHaveBeenCalled();
    expect(snackbarInfo).not.toHaveBeenCalled();
    expect(wrapper.find("select.sel").exists()).toBe(true);
  });
});
