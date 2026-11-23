import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PluginSchema } from "@/__generated__";
import { usePluginStore } from "@/stores/plugins";

const getPlugins = vi.hoisted(() => vi.fn());
const addPlugin = vi.hoisted(() => vi.fn());
const deletePlugin = vi.hoisted(() => vi.fn());

vi.mock("@/services/api/plugin", () => ({
  default: { getPlugins, addPlugin, deletePlugin },
}));

const rommdeck: PluginSchema = {
  id: "rommdeck",
  name: "RommDeck",
  version: "1.0.0",
  actions: [
    {
      id: "open",
      label: "Open in RommDeck",
      url: "rommdeck://open?rom={rom_id}",
      open: "new-tab",
      slot: "game.play",
      platforms: [],
    },
  ],
};

describe("plugin store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getPlugins.mockReset().mockResolvedValue({ data: [] });
    addPlugin.mockReset().mockResolvedValue({ data: rommdeck });
    deletePlugin.mockReset().mockResolvedValue({ data: null });
  });

  it("reads the shelf once per session", async () => {
    await usePluginStore().load();
    await usePluginStore().load();

    expect(getPlugins).toHaveBeenCalledTimes(1);
  });

  it("shows the new plugin after installing one", async () => {
    const store = usePluginStore();
    await store.load();
    getPlugins.mockResolvedValue({ data: [rommdeck] });

    const result = await store.install({ manifest: { id: "rommdeck" } });

    expect(result.ok).toBe(true);
    expect(store.plugins.map((plugin) => plugin.id)).toEqual(["rommdeck"]);
  });

  it("reports why the server refused an install", async () => {
    addPlugin.mockRejectedValue({
      response: { data: { detail: "RommDeck is already installed" } },
    });

    const result = await usePluginStore().install({
      url: "https://example.com",
    });

    expect(result).toEqual({
      ok: false,
      message: "RommDeck is already installed",
    });
  });

  it("drops a plugin from the shelf after removing it", async () => {
    const store = usePluginStore();
    getPlugins.mockResolvedValue({ data: [rommdeck] });
    await store.load();
    getPlugins.mockResolvedValue({ data: [] });

    const result = await store.remove("rommdeck");

    expect(result.ok).toBe(true);
    expect(deletePlugin).toHaveBeenCalledWith("rommdeck");
    expect(store.plugins).toEqual([]);
  });
});
