import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import { saveFixture } from "@/utils/assets.fixtures";
import AssetList from "./AssetList.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    // Keeps the pluralisation count, so a wrong one fails the assertion.
    t: (key: string, count?: number) =>
      typeof count === "number" ? `${key}:${count}` : key,
    locale: "en_US",
  }),
}));

const RBtn = {
  emits: ["click"],
  template: `<button class="fold" @click="$emit('click')"><slot /></button>`,
};
const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};
const RCheckbox = {
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<input type="checkbox" class="check" :checked="modelValue" @change="$emit('update:modelValue', !modelValue)" />`,
};
const stubs = {
  RBtn,
  RTag,
  RCheckbox,
  RIcon: true,
  RAvatar: true,
};

let nextId = 1;
function save(slot: string | null, hoursAgo: number): SaveSchema {
  const id = nextId++;
  const at = new Date(Date.UTC(2026, 8, 16, 12) - hoursAgo * 3600_000);
  return saveFixture({
    id,
    file_name: `save_${id}.srm`,
    updated_at: at.toISOString(),
    slot,
  });
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
    selectable?: boolean;
    checkable?: boolean;
    checkedIds?: ReadonlySet<number>;
  } = {},
) {
  return mount(AssetList, {
    props: { assets: library(), type: "save", ...props },
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
    // Only the middle version is hidden; the count must not include the
    // favorite and the newest, which stay on screen while folded.
    expect(wrapper.get(".fold").text()).toBe("play.show-older-versions:1");

    await wrapper.get(".fold").trigger("click");

    expect(names(wrapper)).toEqual(["save_3.srm", "save_1.srm", "save_2.srm"]);
  });

  it("offers no fold when every version is pinned on screen", () => {
    nextId = 1;
    const newest = save("main_quest", 1);
    const older = { ...save("main_quest", 50), is_favorite: true };
    const wrapper = mountList({ assets: [newest, older] });

    expect(names(wrapper)).toEqual(["save_2.srm", "save_1.srm"]);
    expect(wrapper.findAll(".fold")).toHaveLength(0);
  });

  it("leads each row with a checkbox only when checkable", () => {
    expect(mountList({}).findAll(".check")).toHaveLength(0);

    const wrapper = mountList({ selectable: false, checkable: true });

    expect(wrapper.findAll(".check").length).toBe(names(wrapper).length);
  });

  it("emits the toggled asset and marks the checked row", async () => {
    nextId = 1;
    const only = save("main_quest", 1);
    const wrapper = mountList({
      assets: [only],
      selectable: false,
      checkable: true,
      checkedIds: new Set<number>(),
    });

    await wrapper.get(".check").trigger("change");

    expect(wrapper.emitted("toggle")?.[0]?.[0]).toMatchObject({ id: only.id });
    expect(wrapper.findAll(".r-asset-list__item--checked")).toHaveLength(0);

    const checked = mountList({
      assets: [only],
      selectable: false,
      checkable: true,
      checkedIds: new Set([only.id]),
    });

    expect(checked.findAll(".r-asset-list__item--checked")).toHaveLength(1);
  });

  it("shows every version of a slot while checkable, with no fold control", () => {
    nextId = 1;
    const newest = save("main_quest", 1);
    const middle = save("main_quest", 5);
    const oldest = save("main_quest", 50);
    const assets = [newest, middle, oldest];

    const folded = mountList({ assets });
    expect(names(folded)).toEqual(["save_1.srm"]);
    expect(folded.findAll(".fold")).not.toHaveLength(0);

    const checkable = mountList({
      assets,
      selectable: false,
      checkable: true,
      checkedIds: new Set<number>(),
    });

    expect(names(checkable)).toEqual([
      "save_1.srm",
      "save_2.srm",
      "save_3.srm",
    ]);
    expect(checkable.findAll(".fold")).toHaveLength(0);
  });
});
