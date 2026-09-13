import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import AssetList from "./AssetList.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

const HASH = "0123456789abcdef0123456789abcdef";
const STAMP = "2026-05-13T22:08:00Z";

type Asset = SaveSchema | StateSchema;

function shot(url: string): StateSchema["screenshot"] {
  return { id: 1, download_path: url } as StateSchema["screenshot"];
}

function makeAsset(overrides: Partial<SaveSchema> = {}): Asset {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "slot_1.srm",
    file_name_no_ext: "slot_1",
    file_size_bytes: 4096,
    download_path: "/api/saves/1/content",
    missing_from_fs: false,
    created_at: STAMP,
    updated_at: STAMP,
    emulator: "snes9x",
    screenshot: null,
    ...overrides,
  } as Asset;
}

function mountList(
  assets: Asset[],
  props: {
    type?: "save" | "state";
    selectable?: boolean;
    thumbs?: boolean | null;
  } = {},
) {
  return shallowMount(AssetList, {
    props: { assets, type: "save", selectable: false, ...props },
  });
}

// The leading cell only widens into a 16:9 thumbnail when the list has
// something to show there, and it widens for EVERY row so names stay aligned.
describe("AssetList leading cell", () => {
  it("keeps the icon square when no asset in the list has a screenshot", () => {
    const wrapper = mountList([makeAsset(), makeAsset({ id: 2 })]);

    expect(wrapper.findAll(".r-asset-list__icon")).toHaveLength(2);
    expect(wrapper.findAll(".r-asset-list__icon--thumb")).toHaveLength(0);
    expect(wrapper.findAll(".r-asset-list__shot")).toHaveLength(0);
  });

  it("renders a state's screenshot in the widened cell", () => {
    const wrapper = mountList(
      [makeAsset({ screenshot: shot("/api/screenshots/1/content") })],
      { type: "state" },
    );

    expect(wrapper.findAll(".r-asset-list__icon--thumb")).toHaveLength(1);
    expect(wrapper.find(".r-asset-list__shot").attributes("style")).toContain(
      "/api/screenshots/1/content",
    );
  });

  // Saves carry a screenshot exactly as states do: Save.screenshot and
  // State.screenshot are the same lookup, and the EmulatorJS player uploads one
  // with every in-game save. Gating on `type` would hide it.
  it("renders a save's screenshot too", () => {
    const wrapper = mountList(
      [makeAsset({ screenshot: shot("/api/screenshots/9/content") })],
      { type: "save" },
    );

    expect(wrapper.findAll(".r-asset-list__icon--thumb")).toHaveLength(1);
    expect(wrapper.find(".r-asset-list__shot").attributes("style")).toContain(
      "/api/screenshots/9/content",
    );
  });

  it("widens every row in a mixed list, falling back to the icon", () => {
    const wrapper = mountList([
      makeAsset({ id: 1, screenshot: shot("/api/screenshots/1/content") }),
      makeAsset({ id: 2, screenshot: null }),
    ]);

    expect(wrapper.findAll(".r-asset-list__icon--thumb")).toHaveLength(2);
    expect(wrapper.findAll(".r-asset-list__shot")).toHaveLength(1);
  });

  // Sibling lists that read as one table pass a shared answer, so a section
  // with no captures still lines its names up with the section above it.
  it("lets the parent force the cell wide", () => {
    const wrapper = mountList([makeAsset({ screenshot: null })], {
      thumbs: true,
    });

    expect(wrapper.findAll(".r-asset-list__icon--thumb")).toHaveLength(1);
    expect(wrapper.findAll(".r-asset-list__shot")).toHaveLength(0);
  });

  it("lets the parent force the cell narrow", () => {
    const wrapper = mountList(
      [makeAsset({ screenshot: shot("/api/screenshots/1/content") })],
      { thumbs: false },
    );

    expect(wrapper.findAll(".r-asset-list__icon--thumb")).toHaveLength(0);
  });

  it("keeps the fallback icon type-aware inside a widened cell", () => {
    const withShot = makeAsset({
      id: 1,
      screenshot: shot("/api/screenshots/1/content"),
    });
    const without = makeAsset({ id: 2, screenshot: null });

    const states = mountList([withShot, without], { type: "state" });
    const saves = mountList([withShot, without], { type: "save" });

    const iconOf = (w: ReturnType<typeof mountList>) =>
      w.findAll(".r-asset-list__icon")[1].findComponent({ name: "RIcon" });

    expect(iconOf(states).props("icon")).toBe("mdi-file-outline");
    expect(iconOf(saves).props("icon")).toBe("mdi-content-save");
  });
});

describe("AssetList manage mode", () => {
  // The row name is CSS-truncated and manage mode has no other way to read it.
  it("carries a tooltip when rows are not selectable", () => {
    const wrapper = mountList([makeAsset()], { selectable: false });

    expect(wrapper.findComponent({ name: "RTooltip" }).exists()).toBe(true);
  });

  it("shows a content-hash chip", () => {
    const wrapper = mountList([makeAsset({ content_hash: HASH })]);
    const chips = wrapper.findAllComponents({ name: "HashChip" });

    expect(chips).toHaveLength(1);
    expect(chips[0].props("label")).toBe("rom.content-hash");
    expect(chips[0].props("value")).toBe(HASH);
  });

  it("shows no chip when the asset has no content hash", () => {
    const wrapper = mountList([makeAsset({ content_hash: null })]);

    expect(wrapper.findAllComponents({ name: "HashChip" })).toHaveLength(0);
  });

  // A selectable row is itself a <button>; HashChip is one too, and nesting
  // them is invalid markup.
  it("shows no chip when rows are selectable", () => {
    const wrapper = mountList([makeAsset({ content_hash: HASH })], {
      selectable: true,
    });

    expect(wrapper.findAllComponents({ name: "HashChip" })).toHaveLength(0);
  });

  it("omits the emulator chip entirely when the asset has none", () => {
    const wrapper = mountList([makeAsset({ emulator: null })]);
    const tags = wrapper
      .findAllComponents({ name: "RTag" })
      .map((t) => t.props("text"));

    expect(tags).not.toContain("snes9x");
    expect(tags.every((t) => t)).toBe(true);
  });
});
