import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PluginSchema } from "@/__generated__";
import { usePluginStore } from "@/stores/plugins";
import { romFixture } from "@/utils/rom.fixtures";
import PluginSlot from "./PluginSlot.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api/plugin", () => ({
  default: { getFacts: vi.fn(async () => ({ data: { facts: [] } })) },
}));

const rom = romFixture({
  id: 42,
  name: "Luigi's Mansion",
  platform_slug: "ngc",
});

const plugin = (action: Record<string, unknown> = {}): PluginSchema => ({
  id: "rommdeck",
  name: "RommDeck",
  version: "1.0.0",
  description: null,
  author: null,
  homepage: null,
  actions: [
    {
      id: "open",
      label: "Open in RommDeck",
      icon: "mdi-monitor",
      url: "rommdeck://open?rom={rom_id}",
      open: "new-tab",
      platforms: [],
      ...action,
    },
  ],
});

function render(props: Record<string, unknown> = {}) {
  return mount(PluginSlot, {
    props: { slot: "game.details", rom, size: "default", ...props },
  });
}

describe("PluginSlot", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("renders nothing when the shelf is empty", () => {
    expect(render().findAll("button")).toHaveLength(0);
  });

  it("renders one labelled button per action", () => {
    usePluginStore().plugins = [plugin()];

    const buttons = render().findAll("button");

    expect(buttons).toHaveLength(1);
    expect(buttons[0]?.attributes("aria-label")).toBe("Open in RommDeck");
  });

  it("opens the action's URL in a new tab when it is pressed", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    usePluginStore().plugins = [plugin()];
    const button = render().find("button");

    await button.trigger("click");

    expect(open).toHaveBeenCalledWith(
      "rommdeck://open?rom=42",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("paints the manifest's logo when it has one", () => {
    usePluginStore().plugins = [
      plugin({ image: "https://example.com/logo.png" }),
    ];

    const image = render().find("img");

    expect(image.attributes("src")).toBe("https://example.com/logo.png");
  });

  it("falls back to the icon when there is no logo", () => {
    usePluginStore().plugins = [plugin()];

    expect(render().find("img").exists()).toBe(false);
  });
});
