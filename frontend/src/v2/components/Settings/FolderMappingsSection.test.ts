import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import FolderMappingsSection from "./FolderMappingsSection.vue";

const {
  getSupportedPlatforms,
  addPlatformBindConfig,
  deletePlatformBindConfig,
  addPlatformVersionConfig,
  deletePlatformVersionConfig,
  apiGet,
} = vi.hoisted(() => ({
  getSupportedPlatforms: vi.fn(),
  addPlatformBindConfig: vi.fn(),
  deletePlatformBindConfig: vi.fn(),
  addPlatformVersionConfig: vi.fn(),
  deletePlatformVersionConfig: vi.fn(),
  apiGet: vi.fn(),
}));

vi.mock("@/services/api", () => ({ default: { get: apiGet } }));
vi.mock("@/services/api/platform", () => ({
  default: { getSupportedPlatforms },
}));
vi.mock("@/services/api/config", () => ({
  default: {
    addPlatformBindConfig,
    deletePlatformBindConfig,
    addPlatformVersionConfig,
    deletePlatformVersionConfig,
  },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));
vi.mock("@/v2/composables/usePlatformIconCache", () => ({
  prefetchPlatformIcons: vi.fn(),
}));

const N64 = { id: 1, slug: "n64", name: "Nintendo 64", display_name: "N64" };
const PS2 = { id: 2, slug: "ps2", name: "PlayStation 2", display_name: "PS2" };

interface Row {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: "alias" | "variant" | "auto" | null;
}

// The row list is what the case-sensitive lookup used to get wrong, so the
// stub exposes it and renders the Platform cell the edit actions hang off.
const RTableStub = {
  name: "RTable",
  props: ["items"],
  template:
    '<div><slot v-for="row in items" name="cell.platform" :row="row" /></div>',
};

async function mountWith(folders: string[]) {
  const heartbeat = storeHeartbeat();
  heartbeat.value.FILESYSTEM.FS_PLATFORMS = folders;
  vi.spyOn(heartbeat, "fetchHeartbeat").mockResolvedValue(heartbeat.value);

  const wrapper = mount(FolderMappingsSection, {
    global: {
      stubs: {
        RTable: RTableStub,
        RBtn: true,
        RDialog: true,
        RIcon: true,
        RTextField: true,
        PlatformSelect: true,
        CachedPlatformIcon: true,
      },
    },
  });
  await flushPromises();

  return {
    wrapper,
    rows: wrapper.findComponent(RTableStub).props("items") as Row[],
  };
}

describe("FolderMappingsSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getSupportedPlatforms.mockReset();
    getSupportedPlatforms.mockResolvedValue({ data: [N64, PS2] });
    addPlatformBindConfig.mockReset().mockResolvedValue(undefined);
    deletePlatformBindConfig.mockReset().mockResolvedValue(undefined);
    addPlatformVersionConfig.mockReset().mockResolvedValue(undefined);
    deletePlatformVersionConfig.mockReset().mockResolvedValue(undefined);
    // A refetch echoes the config back, so it neither clears nor changes it.
    apiGet.mockReset();
    apiGet.mockImplementation(() =>
      Promise.resolve({ data: { ...storeConfig().config } }),
    );

    storeAuth().user = { oauth_scopes: ["platforms.write"] } as never;
    storeConfig().config.CONFIG_FILE_WRITABLE = true;
  });

  // The backend lowercases folder names on the way into config.yml, so a
  // folder named "Nintendo 64" is stored as "nintendo 64". Matching the two
  // literally left the mapping invisible and unreachable in the UI.
  it("shows a binding written for a folder whose name is not lowercase", async () => {
    storeConfig().config.PLATFORMS_BINDING = { "nintendo 64": "n64" };

    const { rows } = await mountWith(["Nintendo 64"]);

    expect(rows).toEqual([
      {
        fsSlug: "Nintendo 64",
        slug: "n64",
        displayName: "N64",
        type: "alias",
      },
    ]);
  });

  it("shows a version written for a folder whose name is not lowercase", async () => {
    storeConfig().config.PLATFORMS_VERSIONS = { "playstation 2": "ps2" };

    const { rows } = await mountWith(["PlayStation 2"]);

    expect(rows[0]).toMatchObject({ slug: "ps2", type: "variant" });
  });

  it("marks a folder matching a platform slug as auto-detected whatever its case", async () => {
    const { rows } = await mountWith(["PS2"]);

    expect(rows[0]).toMatchObject({ slug: "ps2", type: "auto" });
  });

  // A mapped row replaces its binding; treating it as auto-detected instead
  // sent a bare add, which the backend used to drop as an existing binding.
  it("replaces the binding when a mapped folder is pointed at another platform", async () => {
    storeConfig().config.PLATFORMS_BINDING = { "nintendo 64": "n64" };

    const { wrapper } = await mountWith(["Nintendo 64"]);
    wrapper
      .findComponent({ name: "FolderMappingPlatformCell" })
      .vm.$emit("select", "ps2");
    await flushPromises();

    expect(deletePlatformBindConfig).toHaveBeenCalledWith({
      fsSlug: "Nintendo 64",
    });
    expect(addPlatformBindConfig).toHaveBeenCalledWith({
      fsSlug: "Nintendo 64",
      slug: "ps2",
    });
  });
});
