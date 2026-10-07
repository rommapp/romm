import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import IndexShell from "./IndexShell.vue";

const smAndDown = ref(false);
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown }),
}));

function mountShell(props: Record<string, unknown> = {}) {
  return mount(IndexShell, {
    props: { listMode: true, listLabel: "Platforms", ...props },
    slots: {
      listHeader: '<div role="row" class="hdr" />',
      listRows: '<div role="row" class="body-row" />',
      default: '<p class="content" />',
    },
  });
}

describe("IndexShell", () => {
  beforeEach(() => {
    smAndDown.value = false;
  });

  it("puts the list header and rows in one named table", () => {
    const table = mountShell().get("[role=table]");

    expect(table.attributes("aria-label")).toBe("Platforms");
    expect(table.find(".hdr").exists()).toBe(true);
    expect(table.find(".body-row").exists()).toBe(true);
    expect(table.find(".content").exists()).toBe(false);
  });

  it("drops the table on phones, where the list is plain links", () => {
    smAndDown.value = true;
    const wrapper = mountShell();

    expect(wrapper.find("[role=table]").exists()).toBe(false);
    expect(wrapper.find(".body-row").exists()).toBe(true);
  });

  it("renders neither list slot outside list mode", () => {
    const wrapper = mountShell({ listMode: false });

    expect(wrapper.find(".hdr").exists()).toBe(false);
    expect(wrapper.find(".body-row").exists()).toBe(false);
    expect(wrapper.find(".content").exists()).toBe(true);
  });
});
