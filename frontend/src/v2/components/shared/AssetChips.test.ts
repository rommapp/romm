import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { saveFixture } from "@/utils/assets.fixtures";
import AssetChips from "./AssetChips.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};

const save = saveFixture({ file_size_bytes: 2048, emulator: "snes9x" });

function chips(props: { latest?: boolean; showEmulator?: boolean } = {}) {
  return mount(AssetChips, {
    props: { asset: save, ...props },
    global: { stubs: { RTag, RIcon: true } },
  });
}

describe("AssetChips", () => {
  it("shows the emulator and the size by default", () => {
    const wrapper = chips();

    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual(["snes9x"]);
    expect(wrapper.get(".r-asset-chips__size").text()).toContain("2 KB");
  });

  it("tags the latest version and can hide the emulator", () => {
    const wrapper = chips({ latest: true, showEmulator: false });

    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "play.latest-version",
    ]);
  });
});
