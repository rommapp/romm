import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import PrevNextNav from "./PrevNextNav.vue";

const { gallery, fromGallery } = vi.hoisted(() => ({
  gallery: { romIdIndex: [] as number[], getRomAt: () => null },
  fromGallery: { value: true },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => gallery,
}));

vi.mock("@/v2/composables/useGalleryProvenance", () => ({
  useGalleryProvenance: () => ({ enteredFromGallery: ref(fromGallery.value) }),
}));

function mountNav(withSlot: boolean) {
  return mount(PrevNextNav, {
    props: { romId: 2 },
    slots: withSlot ? { default: '<div class="cover" />' } : {},
    global: { stubs: { RBtn: { template: "<button />" } } },
  });
}

describe("PrevNextNav", () => {
  beforeEach(() => {
    gallery.romIdIndex = [1, 2, 3];
    fromGallery.value = true;
  });

  it("puts the arrows either side of the slot content", () => {
    const html = mountNav(true).html();
    expect(html.indexOf("<button")).toBeLessThan(html.indexOf("cover"));
    expect(html.lastIndexOf("<button")).toBeGreaterThan(html.indexOf("cover"));
  });

  it("still renders the slot content when there is no list to step through", () => {
    fromGallery.value = false;
    const wrapper = mountNav(true);
    expect(wrapper.find(".cover").exists()).toBe(true);
    expect(wrapper.findAll("button")).toHaveLength(0);
  });

  it("renders nothing without a list or slot content", () => {
    gallery.romIdIndex = [2];
    expect(mountNav(false).html()).toBe("<!--v-if-->");
  });
});
