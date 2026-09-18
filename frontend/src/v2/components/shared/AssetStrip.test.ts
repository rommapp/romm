import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { StateSchema } from "@/__generated__";
import AssetStrip from "./AssetStrip.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};
const stubs = { RTag, RIcon: true, RTooltip: true, RExpandTransition: false };

function state(id: number, emulator: string | null, updated_at: string) {
  return {
    id,
    user_id: 1,
    file_name: `state_${id}.state`,
    file_size_bytes: 1024,
    updated_at,
    emulator,
    screenshot: null,
  } as StateSchema;
}

// Two snes9x states share a timestamp; mgba has one; one is core-less.
const states = [
  state(1, "snes9x", "2026-09-16T10:00:00Z"),
  state(2, "snes9x", "2026-09-16T10:00:00Z"),
  state(3, "mgba", "2026-09-15T10:00:00Z"),
  state(4, null, "2026-09-14T10:00:00Z"),
];

function mountStrip(props: Record<string, unknown> = {}) {
  return mount(AssetStrip, {
    props: { assets: states, type: "state", layout: "flow", ...props },
    global: { stubs },
  });
}

describe("AssetStrip grouped by core", () => {
  it("names each core once and hides the emulator tag on the tiles", () => {
    const wrapper = mountStrip({ groupBy: "emulator" });

    expect(
      wrapper.findAll(".r-asset-group-head__title").map((el) => el.text()),
    ).toEqual(["snes9x", "mgba", "play.any-core"]);
    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "play.latest-version",
    ]);
  });

  it("tags exactly one Latest tile when timestamps tie", () => {
    const wrapper = mountStrip({ groupBy: "emulator" });
    const tagged = wrapper
      .findAll(".r-asset-strip__tile")
      .filter((tile) => tile.find(".tag").exists());

    expect(tagged).toHaveLength(1);
    expect(tagged[0].get(".r-asset-strip__name").text()).toBe("state_1.state");
  });

  it("folds a core nothing can load until its head is clicked", async () => {
    const wrapper = mountStrip({
      groupBy: "emulator",
      disabledReason: (asset: StateSchema) =>
        asset.emulator === "mgba" ? "unsupported" : null,
    });
    const mgba = wrapper.findAll(".r-asset-strip__group")[2];
    const fold = mgba.get(".r-asset-strip__fold");

    expect(mgba.get(".r-asset-group-head__title").text()).toBe("mgba");
    expect(fold.attributes("style")).toContain("display: none");

    await mgba.get(".r-asset-strip__head").trigger("click");

    expect(fold.attributes("style") ?? "").not.toContain("display: none");
  });

  it("shows the emulator tag and no Latest when ungrouped", () => {
    const wrapper = mountStrip();

    expect(wrapper.findAll(".r-asset-group-head__title")).toHaveLength(0);
    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "snes9x",
      "snes9x",
      "mgba",
    ]);
    expect(wrapper.findAll(".r-asset-timestamp")).toHaveLength(4);
  });
});
