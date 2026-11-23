import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";
import type { PluginSchema } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import {
  DEFAULT_PLUGIN_ICON,
  expandPluginUrl,
  gateOpen,
  usePluginActions,
} from "@/composables/usePluginActions";
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

describe("usePluginActions: settings", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("fills a URL from the settings the plugin asked for", () => {
    usePluginStore().plugins = [
      plugin({
        settings: [
          {
            key: "bridge_url",
            label: "Bridge URL",
            type: "url",
            default: "http://127.0.0.1:8050",
          },
        ],
        actions: [
          {
            id: "open",
            label: "Open",
            url: "{setting.bridge_url}/play?rom={rom_id}",
            open: "new-tab",
          },
        ],
      }),
    ];
    usePluginStore().values = {
      rommdeck: { bridge_url: "http://192.168.86.30:8050" },
    };

    const { actions } = withPluginActions((api) => api);

    expect(actions.value[0]?.href).toBe(
      "http://192.168.86.30:8050/play?rom=42",
    );
  });

  it("leaves a stored URL as written rather than encoding it again", () => {
    expect(
      expandPluginUrl("{setting.web}", null, {
        web: "http://host:8780/#library?tab=all",
      }),
    ).toBe("http://host:8780/#library?tab=all");
  });

  it("still encodes the rom's own values inside a longer URL", () => {
    expect(
      expandPluginUrl("{setting.web}/?n={rom_name}", rom, {
        web: "http://host",
      }),
    ).toBe("http://host/?n=Sonic%20%26%20Knuckles");
  });

  it("hides an action until the setting that switches it on is on", () => {
    const gated = plugin({
      settings: [
        { key: "show", label: "Show", type: "boolean", default: false },
      ],
      actions: [
        {
          id: "open",
          label: "Open",
          url: "rommdeck://open?rom={rom_id}",
          open: "new-tab",
          enabled_by: "show",
        },
      ],
    });
    usePluginStore().plugins = [gated];
    usePluginStore().values = { rommdeck: { show: false } };

    expect(withPluginActions((api) => api).actions.value).toEqual([]);

    setActivePinia(createPinia());
    usePluginStore().plugins = [gated];
    usePluginStore().values = { rommdeck: { show: true } };

    expect(withPluginActions((api) => api).actions.value).toHaveLength(1);
  });

  it("treats an ungated action as offered", () => {
    expect(gateOpen(null, {})).toBe(true);
    expect(gateOpen(undefined, {})).toBe(true);
  });

  it("treats a gate whose setting has not been read as open", () => {
    expect(gateOpen("show", {})).toBe(true);
  });

  it("closes only on an explicit no", () => {
    expect(gateOpen("show", { show: false })).toBe(false);
    expect(gateOpen("show", { show: true })).toBe(true);
  });
});

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

    expect(actions.value[0]?.icon).toBe(DEFAULT_PLUGIN_ICON);
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
    expect(
      expandPluginUrl("rommdeck://open?file={file_name}", romFixture()),
    ).toBe("rommdeck://open?file=");
  });
});
