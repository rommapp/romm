import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import GameListHeader from "./GameListHeader.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const smAndDown = ref(false);
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown }),
}));

function mountHeader() {
  return mount(GameListHeader, {
    props: { sortKey: "name", sortDir: "asc" },
    global: { stubs: { RIcon: true, ListSortMenu: true } },
  });
}

describe("GameListHeader", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    smAndDown.value = false;
  });

  it("is a row of column headers, one per column", () => {
    const row = mountHeader().get("[role=row]");
    const headers = row.findAll(":scope > [role=columnheader]");

    expect(headers).toHaveLength(row.element.children.length);
    expect(headers.length).toBeGreaterThan(1);
  });

  it("puts aria-sort on the sortable column headers only", () => {
    const headers = mountHeader().findAll("[role=columnheader]");
    const sorts = headers.map((h) => h.attributes("aria-sort"));

    expect(sorts.filter((s) => s === "ascending")).toHaveLength(1);
    expect(sorts).toContain("none");
    expect(sorts).toContain(undefined);
    expect(mountHeader().findAll("button[aria-sort]")).toHaveLength(0);
  });

  it("names every column header", () => {
    for (const header of mountHeader().findAll("[role=columnheader]")) {
      const name = header.text() || header.find("[aria-label]").exists();
      expect(name, header.html()).toBeTruthy();
    }
  });

  it("is a plain toolbar on phones, outside any grid", () => {
    smAndDown.value = true;
    const wrapper = mountHeader();

    expect(wrapper.find("[role=row]").exists()).toBe(false);
    expect(wrapper.find("[role=columnheader]").exists()).toBe(false);
  });
});
