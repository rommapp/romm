import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import AssetAnnotations from "./AssetAnnotations.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};

const save = { file_size_bytes: 2048, emulator: "snes9x" } as SaveSchema;

function annotations(
  props: { asset?: SaveSchema; showFavorite?: boolean } = {},
) {
  return mount(AssetAnnotations, {
    props: { asset: save, ...props },
    global: { stubs: { RTag, RIcon: true } },
  });
}

describe("AssetAnnotations", () => {
  it("marks a favorited asset and shows every label", () => {
    const wrapper = annotations({
      asset: {
        ...save,
        is_favorite: true,
        labels: ["100% run", "no deaths"],
      } as SaveSchema,
    });

    expect(
      wrapper.get(".r-asset-annotations__fav").attributes("aria-label"),
    ).toBe("rom.favorite");
    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "100% run",
      "no deaths",
    ]);
  });

  it("hides the heart where a favorite toggle already shows it", () => {
    const favorited = { ...save, is_favorite: true } as SaveSchema;

    expect(
      annotations({ asset: favorited })
        .find(".r-asset-annotations__fav")
        .exists(),
    ).toBe(true);
    expect(
      annotations({ asset: favorited, showFavorite: false })
        .find(".r-asset-annotations__fav")
        .exists(),
    ).toBe(false);
  });

  it("renders nothing when the asset carries no marks", () => {
    expect(annotations().find(".r-asset-annotations").exists()).toBe(false);
  });
});
