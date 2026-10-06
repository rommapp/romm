import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeFormatConversions from "@/v2/stores/formatConversions";
import ConvertingIndicator from "./ConvertingIndicator.vue";

vi.mock("vue-i18n");

vi.mock("@v2/lib", () => ({
  RDivider: { template: "<hr />" },
  RIcon: { template: "<i />" },
  RProgressLinear: { template: "<div />" },
  RMenu: {
    template:
      "<div><slot name='activator' :props='{}' /><div class='menu'><slot /></div></div>",
  },
  RMenuItem: {
    props: ["label", "to", "icon"],
    template: "<a class='menu-item'>{{ label }}<slot name='append' /></a>",
  },
}));

function mountIndicator() {
  return mount(ConvertingIndicator, {
    global: { stubs: { Transition: false } },
  });
}

describe("ConvertingIndicator", () => {
  beforeEach(() => {
    const store = storeFormatConversions();
    store.conversions = [];
  });

  it("stays hidden with nothing converting", () => {
    expect(mountIndicator().find(".r-nav-status-pill").exists()).toBe(false);
  });

  it("lists each conversion with its format", () => {
    const store = storeFormatConversions();
    store.add({ href: "/a", romId: 1, romName: "Wipeout", format: "ISO" });
    store.add({ href: "/b", romId: 2, romName: "Lumines", format: "CSO" });

    const wrapper = mountIndicator();

    const items = wrapper.findAll(".menu-item").map((item) => item.text());
    expect(items).toEqual(["WipeoutISO", "LuminesCSO"]);
    expect(wrapper.find(".r-nav-status-pill").text()).toContain("2");
  });

  it("leaves when the last conversion finishes", async () => {
    const store = storeFormatConversions();
    store.add({ href: "/a", romId: 1, romName: "Wipeout", format: "ISO" });
    const wrapper = mountIndicator();
    expect(wrapper.find(".r-nav-status-pill").exists()).toBe(true);

    store.remove("/a");
    await wrapper.vm.$nextTick();

    expect(wrapper.find(".r-nav-status-pill").exists()).toBe(false);
  });
});
