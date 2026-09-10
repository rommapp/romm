import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import AssetPreview from "./AssetPreview.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

const SHOT = "/api/screenshots/1/content";

function makeAsset(screenshot: SaveSchema["screenshot"]): SaveSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "slot_1.srm",
    file_size_bytes: 4096,
    created_at: "2026-05-13T22:08:00Z",
    updated_at: "2026-05-13T22:08:00Z",
    emulator: "mgba",
    screenshot,
  } as SaveSchema;
}

function shot() {
  return { id: 1, download_path: SHOT } as SaveSchema["screenshot"];
}

function mountPreview(
  asset: SaveSchema | StateSchema | null,
  type: "save" | "state",
) {
  return shallowMount(AssetPreview, { props: { asset, type } });
}

// #4422: the stage used to gate the capture on `type === 'state'`, so a save
// that had one showed the floppy medallion instead -- next to an AssetList row
// that rendered the very same capture.
describe("AssetPreview stage", () => {
  it("shows a save's capture rather than the medallion", () => {
    const wrapper = mountPreview(makeAsset(shot()), "save");

    expect(wrapper.find(".r-asset-preview__stage-shot").exists()).toBe(true);
    expect(wrapper.find(".r-asset-preview__save-medallion").exists()).toBe(
      false,
    );
    expect(
      wrapper.find(".r-asset-preview__stage-img").attributes("style"),
    ).toContain(SHOT);
  });

  it("shows a state's capture", () => {
    const wrapper = mountPreview(
      makeAsset(shot()) as unknown as StateSchema,
      "state",
    );

    expect(wrapper.find(".r-asset-preview__stage-shot").exists()).toBe(true);
  });

  it("falls back to the medallion for a save with no capture", () => {
    const wrapper = mountPreview(makeAsset(null), "save");

    expect(wrapper.find(".r-asset-preview__stage-shot").exists()).toBe(false);
    expect(wrapper.find(".r-asset-preview__save-medallion").exists()).toBe(
      true,
    );
  });

  it("falls back to the placeholder for a state with no capture", () => {
    const wrapper = mountPreview(
      makeAsset(null) as unknown as StateSchema,
      "state",
    );

    expect(wrapper.find(".r-asset-preview__stage-shot").exists()).toBe(false);
    expect(wrapper.find(".r-asset-preview__save-medallion").exists()).toBe(
      false,
    );
    expect(wrapper.text()).toContain("play.no-screenshot-available");
  });

  it("shows the empty art when nothing is selected", () => {
    const wrapper = mountPreview(null, "save");

    expect(wrapper.find(".r-asset-preview__empty-art").exists()).toBe(true);
  });
});
