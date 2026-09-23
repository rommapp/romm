import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import SaveDataPanel from "./SaveDataPanel.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

function save(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "game.srm",
    file_name_no_tags: "game",
    file_name_no_ext: "game",
    file_extension: "srm",
    file_path: "saves/ps2",
    file_size_bytes: 2048,
    full_path: "saves/ps2/game.srm",
    download_path: "/api/saves/1/content/game.srm",
    missing_from_fs: false,
    created_at: "2026-09-16T12:00:00Z",
    updated_at: "2026-09-16T12:00:00Z",
    emulator: "retroarch",
    screenshot: null,
    ...overrides,
  };
}

function mountPanel(props: { save: SaveSchema | null }) {
  return mount(SaveDataPanel, {
    props: { platform: "PS2", ...props },
    global: { stubs: { RIcon: true, RTag: true } },
  });
}

describe("SaveDataPanel", () => {
  it("shows a synced save's size and time like the other asset views", () => {
    const wrapper = mountPanel({ save: save() });

    expect(wrapper.find(".r-asset-chips").text()).toContain("KB");
    expect(wrapper.find(".r-asset-timestamp__exact").text()).toMatch(/2026/);
    expect(wrapper.find(".r-v2-save-data__detail").exists()).toBe(false);
  });

  it("falls back to the hint without a save", () => {
    const wrapper = mountPanel({ save: null });

    expect(wrapper.find(".r-asset-timestamp").exists()).toBe(false);
    expect(wrapper.get(".r-v2-save-data__detail").text()).toBe(
      "play.save-data-none-hint",
    );
  });
});
