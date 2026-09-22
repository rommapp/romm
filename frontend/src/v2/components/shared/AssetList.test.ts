import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import AssetList from "./AssetList.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

const RBtn = {
  emits: ["click"],
  template: `<button class="fold" @click="$emit('click')"><slot /></button>`,
};
const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};
const stubs = {
  RBtn,
  RTag,
  RIcon: true,
  RTooltip: true,
  RAvatar: true,
};

let nextId = 1;
function save(slot: string | null, hoursAgo: number): SaveSchema {
  const id = nextId++;
  const at = new Date(Date.UTC(2026, 8, 16, 12) - hoursAgo * 3600_000);
  return {
    id,
    user_id: 1,
    file_name: `save_${id}.srm`,
    file_size_bytes: 1024,
    updated_at: at.toISOString(),
    emulator: null,
    slot,
    screenshot: null,
  } as SaveSchema;
}

function library() {
  nextId = 1;
  return [
    save("main_quest", 30),
    save(null, 500),
    save("autosave", 1),
    save("main_quest", 4),
    save("autosave", 27),
    save("main_quest", 80),
  ];
}

function mountList(
  props: {
    selectedId?: number;
    type?: "save" | "state";
    assets?: SaveSchema[];
  } = {},
) {
  const { assets, ...rest } = props;
  return mount(AssetList, {
    props: { assets: assets ?? library(), type: "save", ...rest },
    global: { stubs },
  });
}

const titles = (wrapper: ReturnType<typeof mountList>) =>
  wrapper.findAll(".r-asset-group-head__title").map((el) => el.text());
const names = (wrapper: ReturnType<typeof mountList>) =>
  wrapper.findAll(".r-asset-list__name").map((el) => el.text());

describe("AssetList slot grouping", () => {
  it("groups saves by slot: autosave first, named by recency, archive last", () => {
    const wrapper = mountList({});

    expect(titles(wrapper)).toEqual([
      "autosave",
      "main_quest",
      "play.slot-none",
    ]);
    expect(wrapper.findAll(".r-asset-group-head__count")).toHaveLength(3);
  });

  it("shows only the newest version per slot until unfolded", async () => {
    const wrapper = mountList({});

    expect(names(wrapper)).toEqual(["save_3.srm", "save_4.srm", "save_2.srm"]);
    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "play.latest-version",
      "play.latest-version",
    ]);

    const folds = wrapper.findAll(".fold");
    expect(folds).toHaveLength(2);
    await folds[1].trigger("click");

    expect(names(wrapper)).toEqual([
      "save_3.srm",
      "save_4.srm",
      "save_1.srm",
      "save_6.srm",
      "save_2.srm",
    ]);
  });

  it("unfolds the slot holding the selected older version", () => {
    const wrapper = mountList({ selectedId: 6 });

    expect(names(wrapper)).toContain("save_6.srm");
    expect(
      wrapper.find(".r-asset-list__item--active .r-asset-list__name").text(),
    ).toBe("save_6.srm");
  });

  it("emits the picked version", async () => {
    const wrapper = mountList({});

    await wrapper.findAll(".r-asset-list__row")[1].trigger("click");

    expect(wrapper.emitted("select")?.[0]?.[0]).toMatchObject({ id: 4 });
  });

  it("renders states as one flat, headerless list", () => {
    const wrapper = mountList({ type: "state" });

    expect(titles(wrapper)).toEqual([]);
    expect(wrapper.findAll(".fold")).toHaveLength(0);
    expect(names(wrapper)).toHaveLength(6);
  });

  it("floats a favorited version to the top of its slot, without folding away the newest", async () => {
    nextId = 1;
    const newest = save("main_quest", 1);
    const middle = save("main_quest", 5);
    const oldest = { ...save("main_quest", 50), is_favorite: true };
    const wrapper = mountList({ assets: [newest, middle, oldest] });

    expect(names(wrapper)).toEqual(["save_3.srm", "save_1.srm"]);
    // "Latest" follows the newest save, not whichever row renders first.
    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "play.latest-version",
    ]);

    await wrapper.get(".fold").trigger("click");

    expect(names(wrapper)).toEqual(["save_3.srm", "save_1.srm", "save_2.srm"]);
  });
});
