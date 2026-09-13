import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SearchCoverSchema, SearchRomSchema } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import SearchCoverDialog from "./SearchCoverDialog.vue";

const { searchCover, searchRom, heartbeat } = vi.hoisted(() => ({
  searchCover: vi.fn(),
  searchRom: vi.fn(),
  heartbeat: {
    value: {
      METADATA_SOURCES: {
        STEAMGRIDDB_API_ENABLED: true,
        STEAM_API_ENABLED: true,
      },
    },
  },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/services/api/sgdb", () => ({ default: { searchCover } }));
vi.mock("@/services/api/rom", () => ({ default: { searchRom } }));
vi.mock("@/stores/heartbeat", () => ({ default: () => heartbeat }));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: vi.fn() }),
}));

const RDialog = {
  props: ["modelValue"],
  template: `<div v-if="modelValue"><slot name="header" /><slot name="content" /></div>`,
};
const RCollapsible = {
  props: ["title"],
  template: `<section class="group" :data-title="title"><slot /></section>`,
};

function cover(
  provider: SearchCoverSchema["provider"],
  url: string,
): SearchCoverSchema {
  return {
    provider,
    name: "Blur",
    resources: [
      {
        thumb: url,
        url,
        type: "static",
        width: 600,
        height: 900,
        style: "",
        author: "",
        score: 0,
        nsfw: false,
        humor: false,
        epilepsy: false,
      },
    ],
  };
}

const rom = {
  id: 5,
  platform_id: 2,
  name: "Blur",
  steam_id: 49800,
} as SimpleRom;

async function openDialog(withRom = false) {
  const emitter: Emitter<Events> = mitt<Events>();
  const picked = vi.fn();
  emitter.on("updateUrlCover", picked);
  const wrapper = mount(SearchCoverDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog,
        RCollapsible,
        RTextField: true,
        RSelect: true,
        RSwitch: true,
        RBtn: true,
        RIcon: true,
        RSpinner: true,
        REmptyState: true,
        RTooltip: true,
      },
    },
  });
  emitter.emit("showSearchCoverDialog", {
    term: "Blur",
    rom: withRom ? rom : undefined,
  });
  await flushPromises();
  return { wrapper, picked };
}

function gridGroups(
  wrapper: Awaited<ReturnType<typeof openDialog>>["wrapper"],
) {
  return wrapper
    .findAll("section.group")
    .map((g) => g.attributes("data-title"));
}

describe("SearchCoverDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchRom.mockResolvedValue({ data: [] });
  });

  it("toggling a provider chip hides its grid and brings it back", async () => {
    searchCover.mockResolvedValue({
      data: [
        cover("sgdb", "https://sgdb/thumb/a.png"),
        cover("steam", "https://steam/a.jpg"),
      ],
    });
    const { wrapper } = await openDialog();

    expect(gridGroups(wrapper)).toEqual(["Blur", "Blur"]);

    const steamChip = wrapper.find("button[aria-pressed]:nth-of-type(2)");
    await steamChip.trigger("click");
    expect(wrapper.findAll("section.group")).toHaveLength(1);

    await steamChip.trigger("click");
    expect(wrapper.findAll("section.group")).toHaveLength(2);
  });

  it("hands a Steam cover off untouched and swaps SteamGridDB thumbs to grids", async () => {
    searchCover.mockResolvedValue({
      data: [
        cover("sgdb", "https://sgdb/thumb/a.png"),
        cover("steam", "https://steam/thumb.jpg"),
      ],
    });
    const { wrapper, picked } = await openDialog();
    const tiles = wrapper.findAll("section.group button");

    await tiles[0].trigger("click");
    expect(picked).toHaveBeenLastCalledWith("https://sgdb/grid/a.png");

    // The dialog closes on pick, so reopen for the second tile.
    const second = await openDialog();
    await second.wrapper.findAll("section.group button")[1].trigger("click");
    expect(second.picked).toHaveBeenLastCalledWith("https://steam/thumb.jpg");
  });

  it("keeps a provider's match cover in the row when its grid came back empty", async () => {
    searchCover.mockResolvedValue({
      data: [cover("sgdb", "https://sgdb/thumb/a.png")],
    });
    searchRom.mockResolvedValue({
      data: [
        {
          steam_id: 49800,
          steam_url_cover: "https://steam/capsule.jpg",
          sgdb_url_cover: "https://sgdb/grid/b.png",
          igdb_url_cover: "https://igdb/c.jpg",
          name: "Blur",
          platform_id: 2,
          is_identified: true,
          is_unidentified: false,
        } as SearchRomSchema,
      ],
    });
    const { wrapper } = await openDialog(true);

    const rowTitles = wrapper
      .findAll("button[title]")
      .map((b) => b.attributes("title"));
    expect(rowTitles).toEqual(["IGDB", "Steam"]);
  });
});
