import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { StateSchema } from "@/__generated__";
import AssetStrip from "./AssetStrip.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

function makeState(id: number): StateSchema {
  return {
    id,
    rom_id: 1,
    user_id: 1,
    file_name: `state_${id}.state`,
    file_size_bytes: 524288,
    download_path: `/api/states/${id}/content`,
    missing_from_fs: false,
    created_at: "2026-05-13T22:08:00Z",
    updated_at: "2026-05-13T22:08:00Z",
    emulator: "snes9x",
    screenshot: null,
  } as StateSchema;
}

function mountStrip(selectedId: number | null = null) {
  return shallowMount(AssetStrip, {
    props: { assets: [makeState(1), makeState(2)], type: "state", selectedId },
  });
}

// #4422: the thumb used to be gated on `type === 'state'`, hiding the capture a
// save carries just as readily.
describe("AssetStrip thumbnails", () => {
  const withShot = (id: number) =>
    ({
      ...makeState(id),
      screenshot: { id, download_path: `/api/screenshots/${id}/content` },
    }) as StateSchema;

  it("shows a save's capture", () => {
    const wrapper = shallowMount(AssetStrip, {
      props: { assets: [withShot(1)], type: "save" },
    });

    expect(
      wrapper.find(".r-asset-strip__thumb-img").attributes("style"),
    ).toContain("/api/screenshots/1/content");
  });

  it("falls back to a type-aware icon when there is no capture", () => {
    const wrapper = shallowMount(AssetStrip, {
      props: { assets: [makeState(1)], type: "save" },
    });

    expect(wrapper.find(".r-asset-strip__thumb-img").exists()).toBe(false);
    expect(
      wrapper
        .find(".r-asset-strip__thumb-icon")
        .findComponent({ name: "RIcon" })
        .props("icon"),
    ).toBe("mdi-content-save");
  });
});

// Every tile is a selection control now that manage mode is gone, so the root
// element and its click path must not quietly become a <div> again.
describe("AssetStrip tiles", () => {
  it("renders each tile as a button", () => {
    const tiles = mountStrip().findAll(".r-asset-strip__tile");

    expect(tiles).toHaveLength(2);
    for (const tile of tiles) {
      expect(tile.element.tagName).toBe("BUTTON");
      expect(tile.attributes("type")).toBe("button");
    }
  });

  it("marks only the selected tile as pressed", () => {
    const tiles = mountStrip(2).findAll(".r-asset-strip__tile");

    expect(tiles[0].attributes("aria-pressed")).toBe("false");
    expect(tiles[1].attributes("aria-pressed")).toBe("true");
  });

  it("emits the asset it was clicked on", async () => {
    const wrapper = mountStrip();

    await wrapper.findAll(".r-asset-strip__tile")[1].trigger("click");

    expect(wrapper.emitted("select")?.[0][0]).toMatchObject({ id: 2 });
  });
});
