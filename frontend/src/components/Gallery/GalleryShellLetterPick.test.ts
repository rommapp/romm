import { flushPromises, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { h, ref, type SetupContext } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import storeGalleryRoms from "@/stores/galleryRoms";
import AlphaJumpMenu from "./AlphaJumpMenu.vue";
import GalleryShell from "./GalleryShell.vue";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("vue-i18n");
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  onBeforeRouteUpdate: vi.fn(),
  onBeforeRouteLeave: vi.fn(),
}));
vi.mock("@/services/api/rom", () => ({ default: { getRoms } }));
// The jump menu only renders on phones and tablets.
vi.mock("@/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({
    xs: ref(false),
    smAndDown: ref(true),
    smAndUp: ref(true),
    mdAndUp: ref(false),
    mdAndDown: ref(true),
    lgAndUp: ref(false),
  }),
}));

const ScrollerStub = {
  name: "RVirtualScroller",
  emits: ["update:viewportRange"],
  setup(_: unknown, { slots, expose }: SetupContext) {
    expose({
      scrollToIndex: vi.fn(),
      scrollTo: vi.fn(),
      containerEl: null,
      scrollTop: 0,
      innerOffsetTop: 0,
    });
    return () => h("div", [slots.prepend?.(), slots.sticky?.()]);
  },
};

const ToolbarStub = {
  name: "GalleryToolbar",
  setup(_: unknown, { slots }: SetupContext) {
    return () => h("div", slots.actions?.());
  },
};

// List rows 0-9 are S, 10-19 are T and 20-29 are U.
async function mountShell() {
  getRoms.mockImplementation(() => new Promise(() => {}));
  const galleryRoms = storeGalleryRoms();
  galleryRoms.currentSearch = true;
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/search", component: { template: "<div />" } }],
  });
  await router.push("/search?orderBy=name&layout=list");
  const wrapper = shallowMount(GalleryShell, {
    props: { hasHeader: false, searchPlaceholder: "", emptyMessage: "" },
    global: {
      plugins: [router],
      stubs: { RVirtualScroller: ScrollerStub, GalleryToolbar: ToolbarStub },
    },
  });
  await flushPromises();
  galleryRoms.total = 30;
  galleryRoms.charIndex = { S: 0, T: 10, U: 20 };
  galleryRoms.metadataLoaded = true;
  galleryRoms.initialFetching = false;
  await flushPromises();

  const scroller = wrapper.findComponent(ScrollerStub);
  const menu = () => wrapper.findComponent(AlphaJumpMenu);
  return {
    galleryRoms,
    current: () => menu().props("current") as string,
    pick: async (letter: string) => {
      menu().vm.$emit("pick", letter);
      await flushPromises();
    },
    show: async (first: number, last: number) => {
      scroller.vm.$emit("update:viewportRange", { first, last });
      await flushPromises();
    },
    userScroll: async () => {
      await scroller.trigger("wheel");
    },
  };
}

describe("GalleryShell jump menu letter", () => {
  it("marks the picked letter when the screen starts with the letter before", async () => {
    const shell = await mountShell();
    await shell.show(6, 13);
    expect(shell.current()).toBe("S");

    await shell.pick("T");
    await shell.show(6, 13);

    expect(shell.current()).toBe("T");
  });

  it("drops an offscreen pick when the jump ends", async () => {
    const shell = await mountShell();
    await shell.pick("T");
    await shell.show(6, 13);
    await shell.show(22, 27);
    await shell.userScroll();
    await shell.show(6, 13);

    expect(shell.current()).toBe("S");
  });

  it("drops the pick once its letter scrolls away", async () => {
    const shell = await mountShell();
    await shell.pick("T");
    await shell.show(6, 13);
    await shell.userScroll();

    await shell.show(22, 27);
    expect(shell.current()).toBe("U");
    await shell.show(6, 13);

    expect(shell.current()).toBe("S");
  });

  it("keeps the pick while the jump settles off its letter", async () => {
    const shell = await mountShell();
    await shell.pick("T");
    await shell.show(6, 13);

    // Rows re-packing under the jump, before it re-anchors on T.
    await shell.show(0, 5);
    await shell.show(6, 13);

    expect(shell.current()).toBe("T");
  });

  it("drops the pick when a different result replaces the gallery", async () => {
    const shell = await mountShell();
    await shell.pick("T");
    await shell.show(6, 13);

    shell.galleryRoms.resultEpoch++;
    await flushPromises();

    expect(shell.current()).toBe("S");
  });
});
