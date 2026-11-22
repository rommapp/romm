import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";
import type { PluginSchema } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import { expandPluginUrl, usePluginActions } from "@/composables/usePluginActions";
import { usePluginStore } from "@/stores/plugins";
import { romFixture } from "@/utils/rom.fixtures";

const rom = romFixture({
  id: 42,
  name: "Sonic & Knuckles",
  platform_slug: "genesis",
  platform_display_name: "Sega Genesis",
  files: [
    {
      id: 1,
      rom_id: 42,
      file_name: "Sonic & Knuckles (USA).md",
    } as never,
  ],
});

const plugin = (overrides: Partial<PluginSchema> = {}): PluginSchema => ({
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
      url: "rommdeck://open?rom={rom_id}&platform={platform_slug}",
      open: "new-tab",
    },
  ],
  ...overrides,
});

/** The composable needs a component to run `onMounted` in. */
function withPluginActions<T>(
  run: (api: ReturnType<typeof usePluginActions>) => T,
  on: SimpleRom = rom,
) {
  let seen: T | undefined;
  const Probe = defineComponent({
    setup() {
      seen = run(usePluginActions(() => on));
      return () => h("div");
    },
  });
  mount(Probe);
  return seen as T;
}

describe("usePluginActions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("offers nothing until a plugin is installed", () => {
    const { actions } = withPluginActions((api) => api);

    expect(actions.value).toEqual([]);
  });

  it("fills the manifest URL with the rom it is offered on", () => {
    usePluginStore().plugins = [plugin()];

    const { actions } = withPluginActions((api) => api);

    expect(actions.value).toHaveLength(1);
    expect(actions.value[0]).toMatchObject({
      pluginId: "rommdeck",
      pluginName: "RommDeck",
      label: "Open in RommDeck",
      icon: "mdi-monitor",
      href: "rommdeck://open?rom=42&platform=genesis",
    });
  });

  it("falls back to a puzzle icon when the manifest names none", () => {
    usePluginStore().plugins = [
      plugin({
        actions: [
          {
            id: "open",
            label: "Open in RommDeck",
            icon: null,
            url: "rommdeck://open?rom={rom_id}",
            open: "new-tab",
          },
        ],
      }),
    ];

    const { actions } = withPluginActions((api) => api);

    expect(actions.value[0]?.icon).toBe("mdi-puzzle-outline");
  });

  it("opens a new-tab action in a new tab", () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    usePluginStore().plugins = [plugin()];
    const { actions, open: run } = withPluginActions((api) => api);

    run(actions.value[0]!);

    expect(open).toHaveBeenCalledWith(
      "rommdeck://open?rom=42&platform=genesis",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("offers an action only on the platforms its manifest names", () => {
    usePluginStore().plugins = [
      plugin({
        actions: [
          {
            id: "open",
            label: "Open in RommDeck",
            icon: null,
            url: "rommdeck://open?rom={rom_id}",
            open: "new-tab",
            platforms: ["ngc", "wii"],
          },
        ],
      }),
    ];

    const onGenesis = withPluginActions((api) => api);
    const onGameCube = withPluginActions(
      (api) => api,
      romFixture({ id: 7, platform_slug: "ngc" }),
    );

    expect(onGenesis.actions.value).toEqual([]);
    expect(onGameCube.actions.value).toHaveLength(1);
  });

  it("matches a platform by the slug its filesystem folder uses", () => {
    usePluginStore().plugins = [
      plugin({
        actions: [
          {
            id: "open",
            label: "Open in RommDeck",
            icon: null,
            url: "rommdeck://open?rom={rom_id}",
            open: "new-tab",
            platforms: ["gc"],
          },
        ],
      }),
    ];

    const { actions } = withPluginActions(
      (api) => api,
      romFixture({ id: 7, platform_slug: "ngc", platform_fs_slug: "gc" }),
    );

    expect(actions.value).toHaveLength(1);
  });

  it("carries the manifest's logo through to the button", () => {
    usePluginStore().plugins = [
      plugin({
        actions: [
          {
            id: "open",
            label: "Open in RommDeck",
            icon: null,
            image: "https://example.com/logo.png",
            url: "rommdeck://open?rom={rom_id}",
            open: "new-tab",
          },
        ],
      }),
    ];

    const { actions } = withPluginActions((api) => api);

    expect(actions.value[0]?.image).toBe("https://example.com/logo.png");
  });
});

describe("expandPluginUrl", () => {
  it("encodes a value that would otherwise break the query string", () => {
    expect(expandPluginUrl("rommdeck://open?name={rom_name}", rom)).toBe(
      "rommdeck://open?name=Sonic%20%26%20Knuckles",
    );
  });

  it("leaves an empty value empty rather than the placeholder", () => {
    expect(expandPluginUrl("rommdeck://open?file={file_name}", romFixture())).toBe(
      "rommdeck://open?file=",
    );
  });
});
