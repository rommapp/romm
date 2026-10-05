import { mount } from "@vue/test-utils";
import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import IndexShell from "@/v2/components/shared/IndexShell.vue";
import CollectionListHeader from "./CollectionListHeader.vue";
import CollectionListRow from "./CollectionListRow.vue";

vi.mock("vue-i18n");

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/v2/components/Collections/CollectionMosaic.vue", () => ({
  default: defineComponent({ template: "<i />" }),
}));

const smAndDown = ref(false);
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown }),
}));

function mountList() {
  return mount(IndexShell, {
    props: { listMode: true, listLabel: "Collections" },
    slots: {
      listHeader: () =>
        h(CollectionListHeader, { sortKey: "name", sortDir: "asc" }),
      listRows: () => [
        h(CollectionListRow, { id: 1, name: "RPGs", to: "/collection/1" }),
        h(CollectionListRow, {
          id: 2,
          name: "Co-op",
          to: "/collection/2",
          kind: "smart",
        }),
      ],
    },
    attachTo: document.body,
  });
}

describe("CollectionListRow", () => {
  beforeEach(() => {
    smAndDown.value = false;
  });

  it("forms a valid table with the list header", async () => {
    const wrapper = mountList();
    try {
      const results = await axe.run(wrapper.element, {
        rules: { "color-contrast": { enabled: false } },
      });
      expect(results.violations.map((v) => v.id)).toEqual([]);
    } finally {
      wrapper.unmount();
    }
  });

  it("is a row of cells with one link to the collection", () => {
    const row = mount(CollectionListRow, {
      props: { id: 1, name: "RPGs", to: "/collection/1" },
    });

    expect(row.attributes("role")).toBe("row");
    expect(row.findAll(":scope > [role=cell]")).toHaveLength(
      row.element.children.length,
    );
    expect(row.findAll("a").map((a) => a.attributes("href"))).toEqual([
      "/collection/1",
    ]);
  });
});
