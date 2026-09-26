import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { makeRom } from "@/utils/rom.fixtures";
import ScanPlatformRow from "./ScanPlatformRow.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({ toWebp: (src: string) => src }),
}));

const RTooltip = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tip" :data-text="text"><slot name="activator" :props="{}" /></span>`,
};

describe("ScanPlatformRow", () => {
  it("names each provider match in a RomM tooltip, not a native title", () => {
    const wrapper = mount(ScanPlatformRow, {
      props: {
        rom: makeRom({ id: 1, is_identified: true, igdb_id: 1, ss_id: 2 }),
      },
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
          RImg: true,
          RTooltip,
        },
      },
    });

    const tips = wrapper.findAll(".tip");
    expect(tips.map((tip) => tip.attributes("data-text"))).toEqual([
      "IGDB match",
      "ScreenScraper match",
    ]);
    for (const badge of wrapper.findAll(".r-v2-scan-platform__provider")) {
      expect(badge.attributes("title")).toBeUndefined();
    }
  });
});
