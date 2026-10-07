import { mount } from "@vue/test-utils";
import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import IndexShell from "@/v2/components/shared/IndexShell.vue";
import PlatformListHeader from "./PlatformListHeader.vue";
import PlatformListRow from "./PlatformListRow.vue";

vi.mock("vue-i18n");

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/v2/components/shared/PlatformIcon.vue", () => ({
  default: defineComponent({ template: "<i />" }),
}));

vi.mock("@/v2/composables/usePlatformPlayable", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/v2/composables/usePlatformPlayable")
  >()),
  usePlatformPlayable: () => ({
    emulator: ref(null),
    mode: ref(null),
    streamLabel: ref(null),
  }),
}));

const smAndDown = ref(false);
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown }),
}));

function mountList() {
  return mount(IndexShell, {
    props: { listMode: true, listLabel: "Platforms" },
    slots: {
      listHeader: () =>
        h(PlatformListHeader, { sortKey: "name", sortDir: "asc" }),
      listRows: () => [
        h(PlatformListRow, { id: 1, slug: "snes", displayName: "SNES" }),
        h(PlatformListRow, { id: 2, slug: "n64", displayName: "N64" }),
      ],
    },
    attachTo: document.body,
  });
}

describe("PlatformListRow", () => {
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

  it("is a row of cells with one link to the platform", () => {
    const row = mount(PlatformListRow, {
      props: { id: 1, slug: "snes", displayName: "SNES" },
    });

    expect(row.attributes("role")).toBe("row");
    expect(row.findAll(":scope > [role=cell]")).toHaveLength(
      row.element.children.length,
    );
    expect(row.findAll("a").map((a) => a.attributes("href"))).toEqual([
      "/platform/1",
    ]);
  });

  it("stays a single link on phones", () => {
    smAndDown.value = true;
    const row = mount(PlatformListRow, {
      props: { id: 1, slug: "snes", displayName: "SNES" },
    });

    expect(row.element.tagName).toBe("A");
    expect(row.attributes("role")).toBeUndefined();
  });
});
