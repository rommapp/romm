import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PluginSettingField from "./PluginSettingField.vue";

vi.mock("vue-i18n");

const getOptions = vi.fn();

vi.mock("@/services/api/plugin", () => ({
  default: {
    getOptions: (...args: unknown[]) => getOptions(...args),
  },
}));

vi.mock("@/lib", () => ({
  RIcon: { template: `<i />` },
  RBtn: { template: `<button class="btn"><slot /></button>` },
  RSwitch: {
    props: ["modelValue", "label"],
    emits: ["update:modelValue"],
    template: `<button class="switch" />`,
  },
  RSelect: {
    name: "RSelect",
    props: {
      modelValue: { type: [String, Number], default: "" },
      items: { type: Array, default: () => [] },
      searchable: { type: Boolean, default: false },
      loading: { type: Boolean, default: false },
      placeholder: { type: String, default: "" },
    },
    emits: ["update:modelValue", "update:search"],
    template: `<div class="select">{{ items ? items.length : 0 }}</div>`,
  },
  RTextField: {
    props: ["modelValue", "type", "placeholder"],
    emits: ["update:modelValue"],
    template: `<input class="text" />`,
  },
}));

const DEVICES = {
  data: {
    options: [
      { value: "82f3e2fe", label: "AYANEO KONKR Pocket FIT" },
      { value: "e4394fe4", label: "AYN Thor Max" },
    ],
  },
};

function searchSetting() {
  return {
    key: "handheld",
    label: "Your handheld",
    type: "search" as const,
    source: {
      url: "https://example.com/devices",
      query: {},
      items: "devices",
      value: "id",
      label: "{brandName} {modelName}",
      limit: 20,
    },
  };
}

function groupSetting() {
  return {
    key: "pc_setups",
    label: "Your PC setups",
    type: "groups" as const,
    max_items: 2,
    fields: [
      { key: "name", label: "Name", type: "text" as const },
      { key: "memory", label: "Memory (GB)", type: "number" as const },
    ],
  };
}

beforeEach(() => {
  getOptions.mockReset();
  getOptions.mockResolvedValue(DEVICES);
});

describe("PluginSettingField: a searched field", () => {
  it("asks the plugin's source for choices when it appears", async () => {
    mount(PluginSettingField, {
      props: {
        setting: searchSetting(),
        modelValue: "",
        pluginId: "emuready",
      },
    });
    await flushPromises();

    expect(getOptions).toHaveBeenCalledWith("emuready", "handheld", "");
  });

  it("hands the choices to the control as items", async () => {
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: searchSetting(),
        modelValue: "",
        pluginId: "emuready",
      },
    });
    await flushPromises();

    // Two devices came back, so the control has two items to offer.
    expect(wrapper.find(".select").text()).toBe("2");
    expect(wrapper.findComponent({ name: "RSelect" }).props("searchable")).toBe(
      true,
    );
  });

  it("keeps the chosen item after the search moves on", async () => {
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: searchSetting(),
        modelValue: "e4394fe4",
        pluginId: "emuready",
      },
    });
    await flushPromises();

    // The first page was asked for, and it holds the saved choice with its
    // name, which is what makes the control show the choice rather than look
    // cleared the moment a new search replaces the list.
    const select = wrapper.findComponent({ name: "RSelect" });
    expect(select.props("items")).toContainEqual({
      title: "AYN Thor Max",
      value: "e4394fe4",
    });
  });

  it("hands the chosen id up and never clears it by itself", async () => {
    const wrapper = mount(PluginSettingField, {
      props: { setting: searchSetting(), modelValue: "", pluginId: "emuready" },
    });
    await flushPromises();

    const select = wrapper.findComponent({ name: "RSelect" });
    select.vm.$emit("update:modelValue", "e4394fe4");
    await flushPromises();

    // The id is what gets saved; nothing here may replace it with an empty one.
    expect(wrapper.emitted("update:modelValue")).toEqual([["e4394fe4"]]);
  });

  it("shows the saved choice after the list is replaced", async () => {
    const wrapper = mount(PluginSettingField, {
      props: { setting: searchSetting(), modelValue: "", pluginId: "emuready" },
    });
    await flushPromises();

    // The user picks one, the parent stores it, and a later search returns a
    // list that does not mention it: the control still shows what was chosen.
    getOptions.mockResolvedValue({ data: { options: [] } });
    await wrapper.setProps({ modelValue: "e4394fe4" });

    const select = wrapper.findComponent({ name: "RSelect" });
    expect(select.props("modelValue")).toBe("e4394fe4");
    expect(select.props("items")).toContainEqual({
      title: "AYN Thor Max",
      value: "e4394fe4",
    });
  });

  it("says so when the source cannot be reached", async () => {
    getOptions.mockRejectedValue(new Error("nope"));
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: searchSetting(),
        modelValue: "",
        pluginId: "emuready",
      },
    });
    await flushPromises();

    expect(wrapper.find(".plugin-field__note").exists()).toBe(true);
  });

  it("shows the source's note in place of the list", async () => {
    getOptions.mockResolvedValue({ data: { options: [], note: "timed out" } });
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: searchSetting(),
        modelValue: "",
        pluginId: "emuready",
      },
    });
    await flushPromises();

    expect(wrapper.find(".plugin-field__note").text()).toBe("timed out");
  });
});

describe("PluginSettingField: a list of entries", () => {
  it("draws one block per saved entry", () => {
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: groupSetting(),
        modelValue: [{ name: "Living room", memory: 32 }],
        pluginId: "emuready",
      },
    });

    expect(wrapper.findAll(".plugin-field__entry")).toHaveLength(1);
  });

  it("adds an entry with each field empty", async () => {
    const wrapper = mount(PluginSettingField, {
      props: { setting: groupSetting(), modelValue: [], pluginId: "emuready" },
    });

    await wrapper.find(".btn").trigger("click");

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual([
      { name: "", memory: undefined },
    ]);
  });

  it("removes an entry", async () => {
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: groupSetting(),
        modelValue: [{ name: "a" }, { name: "b" }],
        pluginId: "emuready",
      },
    });

    const remove = wrapper.findAll(".plugin-field__entry .btn")[0]!;
    await remove.trigger("click");

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual([
      { name: "b" },
    ]);
  });

  it("stops at the manifest's limit", () => {
    const wrapper = mount(PluginSettingField, {
      props: {
        setting: groupSetting(),
        modelValue: [{ name: "a" }, { name: "b" }],
        pluginId: "emuready",
      },
    });

    // The add button is the last one; with two of two entries it is gone.
    expect(wrapper.findAll(".btn")).toHaveLength(2);
  });
});
