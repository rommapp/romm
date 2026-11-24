import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import PluginStoreBrowse from "./PluginStoreBrowse.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/lib", () => ({
  RIcon: { template: `<i class="icon" />` },
  RChip: {
    props: ["size", "variant"],
    template: `<span class="chip"><slot /></span>`,
  },
  RBtn: {
    props: ["variant", "color", "size", "disabled"],
    emits: ["click"],
    template: `<button class="btn" @click="$emit('click')"><slot /></button>`,
  },
  RDialog: {
    props: ["modelValue", "icon", "width", "cancelable"],
    template: `<div class="dialog"><slot name="header" /><slot name="content" /><slot name="footer" /></div>`,
  },
  RTextField: {
    props: ["modelValue", "placeholder"],
    emits: ["update:modelValue"],
    template: `<input class="search" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
  },
}));

const entries = [
  {
    id: "rommdeck",
    name: "RommDeck",
    version: "1.1.0",
    description: "Open a game on the machine RommDeck manages.",
    author: "jkoehler11",
    homepage: "https://example.com/rommdeck",
    manifest_url: "https://example.com/rommdeck.json",
    tags: ["launcher", "emulation"],
  },
  {
    id: "emuready",
    name: "EmuReady",
    version: "1.6.0",
    description: "Compatibility reports for this game.",
    author: "jkoehler11",
    homepage: null,
    manifest_url: "https://example.com/emuready.json",
    tags: ["compatibility", "emulation"],
  },
  {
    id: "gallery",
    name: "Gallery",
    version: "0.1.0",
    description: "A screenshot browser.",
    author: "someone",
    homepage: null,
    manifest_url: "https://example.com/gallery.json",
    tags: ["media"],
  },
];

function mountStore(installedIds: string[] = []) {
  return mount(PluginStoreBrowse, {
    props: {
      open: true,
      entries,
      installedIds,
      busyId: "",
      problem: "",
    },
  });
}

const names = (wrapper: ReturnType<typeof mountStore>) =>
  wrapper.findAll(".card__name").map((node) => node.text());

describe("PluginStoreBrowse: finding a plugin", () => {
  it("shows every entry it was given", () => {
    expect(names(mountStore())).toEqual(["RommDeck", "EmuReady", "Gallery"]);
  });

  it("narrows to what was typed", async () => {
    const wrapper = mountStore();
    await wrapper.find(".search").setValue("compat");

    expect(names(wrapper)).toEqual(["EmuReady"]);
  });

  it("matches a tag as well as a name", async () => {
    const wrapper = mountStore();
    await wrapper.find(".search").setValue("emulation");

    expect(names(wrapper)).toEqual(["RommDeck", "EmuReady"]);
  });

  it("narrows to a tag that was picked", async () => {
    const wrapper = mountStore();
    const media = wrapper
      .findAll(".store__tag")
      .find((b) => b.text() === "media");
    await media!.trigger("click");

    expect(names(wrapper)).toEqual(["Gallery"]);
  });

  it("picks the same tag again to let it go", async () => {
    const wrapper = mountStore();
    const media = wrapper
      .findAll(".store__tag")
      .find((b) => b.text() === "media");
    await media!.trigger("click");
    await media!.trigger("click");

    expect(names(wrapper)).toEqual(["RommDeck", "EmuReady", "Gallery"]);
  });

  it("says when nothing matches", async () => {
    const wrapper = mountStore();
    await wrapper.find(".search").setValue("nothing here");

    expect(wrapper.find(".store__empty").text()).toBe(
      "settings.plugins-store-nothing",
    );
  });
});

describe("PluginStoreBrowse: installing", () => {
  it("offers an install for what is not installed", () => {
    const wrapper = mountStore(["rommdeck"]);
    const buttons = wrapper
      .findAll(".btn")
      .filter((b) => b.text() === "settings.plugins-install");

    expect(buttons).toHaveLength(2);
  });

  it("says installed instead of offering it again", () => {
    const installed = mountStore(["rommdeck"])
      .findAll(".chip")
      .map((c) => c.text());

    expect(installed).toContain("settings.plugins-installed");
  });

  it("hands the id up when install is pressed", async () => {
    const wrapper = mountStore();
    const install = wrapper
      .findAll(".btn")
      .find((b) => b.text() === "settings.plugins-install");
    await install!.trigger("click");

    expect(wrapper.emitted("install")).toEqual([["rommdeck"]]);
  });

  it("shows the problem and offers to try again", () => {
    const wrapper = mount(PluginStoreBrowse, {
      props: {
        open: true,
        entries,
        installedIds: [],
        busyId: "",
        problem: "The store could not be read",
      },
    });

    expect(wrapper.find(".store__problem").text()).toContain(
      "The store could not be read",
    );
  });
});
