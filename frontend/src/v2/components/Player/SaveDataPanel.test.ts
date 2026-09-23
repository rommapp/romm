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
    file_name: "game.srm",
    file_size_bytes: 2048,
    updated_at: "2026-09-16T12:00:00Z",
    emulator: "retroarch",
    ...overrides,
  } as SaveSchema;
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
