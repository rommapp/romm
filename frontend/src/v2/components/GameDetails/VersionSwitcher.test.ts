import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { DetailedRom } from "@/stores/roms";
import VersionSwitcher from "./VersionSwitcher.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

// The RA mark and the default-version bookmark both live in RMenuItem's
// `append` slot, so the stub has to render it.
const RMenuItem = {
  props: ["label"],
  template: `<li class="item">{{ label }}<slot name="append" /></li>`,
};
const RMenu = {
  template: `<div><slot name="activator" :props="{}" /><slot /></div>`,
};
const RBtn = { template: `<button><slot /></button>` };
const RIcon = { props: ["icon"], template: `<i class="icon" :class="icon" />` };
const RTooltip = {
  props: ["text", "activator"],
  template: `<span class="tooltip" :data-text="text" :data-activator="activator" />`,
};

type Sibling = {
  id: number;
  fs_name_no_ext: string;
  ra_hash_match: boolean | null;
};

function mountSwitcher(rom: {
  id: number;
  fs_name_no_ext: string;
  ra_hash_match: boolean | null;
  siblings: Sibling[];
  achievements?: number;
}) {
  return mount(VersionSwitcher, {
    props: {
      rom: {
        id: rom.id,
        fs_name_no_ext: rom.fs_name_no_ext,
        ra_hash_match: rom.ra_hash_match,
        merged_ra_metadata: {
          achievements: Array.from(
            { length: rom.achievements ?? 3 },
            () => ({}),
          ),
        },
        rom_user: { is_main_sibling: false },
        sibling_roms: rom.siblings.map((s) => ({
          ...s,
          is_main_sibling: false,
        })),
      } as unknown as DetailedRom,
    },
    global: { stubs: { RMenu, RMenuItem, RBtn, RIcon, RTooltip } },
  });
}

// Maps each menu row to whether it carries the RA mark, keyed by label.
function raByVersion(wrapper: ReturnType<typeof mountSwitcher>) {
  return Object.fromEntries(
    wrapper
      .findAll(".item")
      .map((w) => [w.text(), w.find(".version-switcher__ra").exists()]),
  );
}

describe("VersionSwitcher RetroAchievements support", () => {
  // RA hashes one dump per release, so the menu has to say which one
  // without the user opening each version.
  it("marks only the versions RetroAchievements matched", () => {
    const wrapper = mountSwitcher({
      id: 1,
      fs_name_no_ext: "Star Fox 64 (USA)",
      ra_hash_match: true,
      siblings: [
        {
          id: 2,
          fs_name_no_ext: "Star Fox 64 (USA) (Rev 1)",
          ra_hash_match: false,
        },
      ],
    });

    expect(raByVersion(wrapper)).toEqual({
      "Star Fox 64 (USA)": true,
      "Star Fox 64 (USA) (Rev 1)": false,
    });
  });

  it("marks a sibling even when the version in view is unmatched", () => {
    const wrapper = mountSwitcher({
      id: 1,
      fs_name_no_ext: "Star Fox 64 (USA)",
      ra_hash_match: false,
      siblings: [
        {
          id: 2,
          fs_name_no_ext: "Star Fox 64 (USA) (Rev 1)",
          ra_hash_match: true,
        },
      ],
    });

    expect(raByVersion(wrapper)).toEqual({
      "Star Fox 64 (USA)": false,
      "Star Fox 64 (USA) (Rev 1)": true,
    });
  });

  // Claiming support RA never confirmed is worse than staying quiet.
  it("leaves rows unmarked when support was never checked", () => {
    const wrapper = mountSwitcher({
      id: 1,
      fs_name_no_ext: "Game (USA)",
      ra_hash_match: null,
      siblings: [
        { id: 2, fs_name_no_ext: "Game (Europe)", ra_hash_match: null },
      ],
    });

    expect(wrapper.findAll(".version-switcher__ra")).toHaveLength(0);
  });

  // RA's hash list includes games it has no achievements for, so a hash
  // match alone would promise unlocks that can never happen.
  it("marks nothing when the game has no achievements", () => {
    const wrapper = mountSwitcher({
      id: 1,
      fs_name_no_ext: "Star Fox 64 (USA)",
      ra_hash_match: true,
      achievements: 0,
      siblings: [
        {
          id: 2,
          fs_name_no_ext: "Star Fox 64 (USA) (Rev 1)",
          ra_hash_match: true,
        },
      ],
    });

    expect(wrapper.findAll(".version-switcher__ra")).toHaveLength(0);
  });

  // A native `title` would drop keyboard reveal and touch handling, and
  // RTooltip costs no width here, so the mark keeps a real tooltip anchored
  // to itself rather than to the whole row.
  it("explains the mark with an RTooltip bound to the mark", () => {
    const wrapper = mountSwitcher({
      id: 1,
      fs_name_no_ext: "Star Fox 64 (USA)",
      ra_hash_match: true,
      siblings: [
        {
          id: 2,
          fs_name_no_ext: "Star Fox 64 (USA) (Rev 1)",
          ra_hash_match: false,
        },
      ],
    });

    const tooltip = wrapper.find(".version-switcher__ra .tooltip");
    expect(tooltip.exists()).toBe(true);
    expect(tooltip.attributes("data-activator")).toBe("parent");
    expect(tooltip.attributes("data-text")).toBe(
      "rom.retroachievements-supported",
    );
    expect(wrapper.find(".version-switcher__ra img").attributes("title")).toBe(
      undefined,
    );
  });
});
