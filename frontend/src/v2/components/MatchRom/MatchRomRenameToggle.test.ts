import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { makeRom } from "@/utils/rom.fixtures";
import MatchRomRenameToggle from "./MatchRomRenameToggle.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const rom = makeRom({
  fs_name: "Zelda (USA).gba",
  fs_name_no_tags: "Zelda",
});

function mountToggle(matchedName: string) {
  return mount(MatchRomRenameToggle, {
    props: { modelValue: false, rom, matchedName },
    global: { stubs: { RIcon: true, RSwitch: true } },
  });
}

describe("MatchRomRenameToggle", () => {
  it("previews the rename when the matched name differs", () => {
    const wrapper = mountToggle("The Legend of Zelda");
    expect(wrapper.find(".rename-toggle").exists()).toBe(true);
    expect(wrapper.get(".rename-toggle__name--new").text()).toBe(
      "The Legend of Zelda (USA).gba",
    );
  });

  it("hides when the file name would not change", () => {
    const wrapper = mountToggle("Zelda");
    expect(wrapper.find(".rename-toggle").exists()).toBe(false);
  });
});
