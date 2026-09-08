import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ScanPriorityList from "./ScanPriorityList.vue";

// vue-i18n's `t` is stubbed to echo the key so the component mounts without
// the full i18n plugin.
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const SOURCES = [
  { value: "igdb", label: "IGDB" },
  { value: "moby", label: "MobyGames" },
  { value: "ss", label: "ScreenScraper" },
  { value: "ra", label: "RetroAchievements" },
];

const CODES = [
  { value: "us", label: "us" },
  { value: "eu", label: "eu" },
  { value: "jp", label: "jp" },
];

// Stub RBtn as a plain <button> and RTextField as a plain <input> so
// clicks, typing and the disabled state work without pulling in the full
// primitives; RIcon renders nothing.
const STUBS = {
  RIcon: true,
  RBtn: {
    props: ["disabled"],
    emits: ["click"],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  RTextField: {
    props: ["modelValue", "disabled"],
    emits: ["update:modelValue"],
    template:
      '<input :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
};

function mountList(modelValue: string[]) {
  return mount(ScanPriorityList, {
    props: { modelValue, sources: SOURCES },
    global: { stubs: STUBS },
  });
}

function mountCustomList(modelValue: string[]): ReturnType<typeof mountList> {
  return mount(ScanPriorityList, {
    props: { modelValue, sources: CODES, allowCustom: true },
    global: { stubs: STUBS },
  });
}

// The free-text field is the only <input> the component renders.
async function type(wrapper: ReturnType<typeof mountList>, value: string) {
  await wrapper.find("input").setValue(value);
}

function lastEmit(wrapper: ReturnType<typeof mountList>): string[] {
  const events = wrapper.emitted("update:modelValue");
  expect(events).toBeTruthy();
  return events!.at(-1)![0] as string[];
}

describe("ScanPriorityList", () => {
  it("lists enabled sources in priority order and the rest in the tray", () => {
    const wrapper = mountList(["igdb", "moby"]);
    const rows = wrapper.findAll(".r-v2-spl__row");
    expect(rows.map((r) => r.find(".r-v2-spl__label").text())).toEqual([
      "IGDB",
      "MobyGames",
    ]);
    // Remaining sources become "add" chips.
    const tray = wrapper.findAll(".r-v2-spl__add");
    expect(tray.map((b) => b.text())).toEqual([
      "ScreenScraper",
      "RetroAchievements",
    ]);
  });

  it("moves a source down", async () => {
    const wrapper = mountList(["igdb", "moby", "ss"]);
    // Row 0 action buttons: [up, down, remove]; down is index 1.
    await wrapper
      .findAll(".r-v2-spl__row")[0]
      .findAll("button")[1]
      .trigger("click");
    expect(lastEmit(wrapper)).toEqual(["moby", "igdb", "ss"]);
  });

  it("moves a source up", async () => {
    const wrapper = mountList(["igdb", "moby", "ss"]);
    // Row 2 up button is index 0.
    await wrapper
      .findAll(".r-v2-spl__row")[2]
      .findAll("button")[0]
      .trigger("click");
    expect(lastEmit(wrapper)).toEqual(["igdb", "ss", "moby"]);
  });

  it("disables (removes) a source", async () => {
    const wrapper = mountList(["igdb", "moby", "ss"]);
    // Row 1 remove button is index 2.
    await wrapper
      .findAll(".r-v2-spl__row")[1]
      .findAll("button")[2]
      .trigger("click");
    expect(lastEmit(wrapper)).toEqual(["igdb", "ss"]);
  });

  it("appends a source from the tray", async () => {
    const wrapper = mountList(["igdb"]);
    // Tray keeps the canonical `sources` order minus enabled: moby, ss, ra.
    await wrapper.findAll(".r-v2-spl__add")[1].trigger("click");
    expect(lastEmit(wrapper)).toEqual(["igdb", "ss"]);
  });

  it("has no free-text field unless allow-custom is set", () => {
    expect(mountList(["igdb"]).find("input").exists()).toBe(false);
  });

  it("does not move the first source up or the last source down", () => {
    const wrapper = mountList(["igdb", "moby"]);
    const rows = wrapper.findAll(".r-v2-spl__row");
    // First row's up button and last row's down button are disabled.
    expect(
      (rows[0].findAll("button")[0].element as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (rows[1].findAll("button")[1].element as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});

describe("ScanPriorityList with allow-custom", () => {
  it("appends a typed code on Enter, lowercased", async () => {
    const wrapper = mountCustomList(["us"]);
    await type(wrapper, " BR ");
    await wrapper.find("input").trigger("keydown.enter");
    expect(lastEmit(wrapper)).toEqual(["us", "br"]);
  });

  it("appends a typed code from the add button", async () => {
    const wrapper = mountCustomList(["us"]);
    await type(wrapper, "jp");
    // The add button is the only one outside the rows.
    await wrapper.find(".r-v2-spl__entry button").trigger("click");
    expect(lastEmit(wrapper)).toEqual(["us", "jp"]);
  });

  it("splits a comma-separated list and skips duplicates", async () => {
    const wrapper = mountCustomList(["us"]);
    await type(wrapper, "eu, jp, US, eu");
    await wrapper.find("input").trigger("keydown.enter");
    expect(lastEmit(wrapper)).toEqual(["us", "eu", "jp"]);
  });

  it("emits nothing when the typed code is already listed", async () => {
    const wrapper = mountCustomList(["us"]);
    await type(wrapper, "us");
    await wrapper.find("input").trigger("keydown.enter");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("lists custom codes absent from the suggestions", () => {
    const wrapper = mountCustomList(["wor", "us"]);
    const rows = wrapper.findAll(".r-v2-spl__row");
    expect(rows.map((r) => r.find(".r-v2-spl__label").text())).toEqual([
      "wor",
      "us",
    ]);
    // Suggestions drop the codes already listed.
    expect(wrapper.findAll(".r-v2-spl__add").map((b) => b.text())).toEqual([
      "eu",
      "jp",
    ]);
  });
});
