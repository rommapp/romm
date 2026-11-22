import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import BackToTopButton from "./BackToTopButton.vue";

vi.mock("vue-i18n");

const { viewport } = vi.hoisted(() => ({
  viewport: { height: null as unknown as { value: number } },
}));
vi.mock("@vueuse/core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@vueuse/core")>()),
  useWindowSize: () => ({ width: ref(1280), height: viewport.height }),
}));

const reducedMotion = { value: false };
vi.mock("@/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: reducedMotion }),
}));

let scrollTo: ReturnType<typeof vi.fn>;

beforeEach(() => {
  viewport.height = ref(800);
  scrollTo = vi.fn();
  vi.spyOn(window, "scrollTo").mockImplementation(
    scrollTo as unknown as typeof window.scrollTo,
  );
});

function makeRoot() {
  const el = document.createElement("div");
  const first = document.createElement("button");
  first.className = "first";
  el.appendChild(first);
  document.body.appendChild(el);
  return el;
}

function mountButton(root: HTMLElement, scrollTop: number) {
  return mount(BackToTopButton, {
    attachTo: document.body,
    props: { root, scrollTop },
    global: { stubs: { transition: false } },
  });
}

function setPageScroll(top: number) {
  Object.defineProperty(window, "scrollY", { value: top, configurable: true });
}

afterEach(() => {
  document.body.innerHTML = "";
  reducedMotion.value = false;
  setPageScroll(0);
  vi.restoreAllMocks();
});

describe("BackToTopButton", () => {
  it("stays hidden within the first viewport", () => {
    const wrapper = mountButton(makeRoot(), 400);
    expect(wrapper.find("button").exists()).toBe(false);
  });

  it("shows once scrolled past a viewport", async () => {
    const wrapper = mountButton(makeRoot(), 400);
    await wrapper.setProps({ scrollTop: 1200 });
    expect(wrapper.get("button").attributes("aria-label")).toBe(
      "gallery.back-to-top",
    );
  });

  it("smooth-scrolls the page to the top and emits", async () => {
    const wrapper = mountButton(makeRoot(), 1200);
    await wrapper.get("button").trigger("click");
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
    expect(wrapper.emitted("scroll-to-top")).toHaveLength(1);
  });

  it("jumps without animation under reduced motion", async () => {
    reducedMotion.value = true;
    const wrapper = mountButton(makeRoot(), 1200);
    await wrapper.get("button").trigger("click");
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "auto" });
  });

  it("follows a viewport resize without a scroll", async () => {
    const wrapper = mountButton(makeRoot(), 1000);
    expect(wrapper.find("button").exists()).toBe(true);

    viewport.height.value = 1200;
    await wrapper.vm.$nextTick();

    expect(wrapper.find("button").exists()).toBe(false);
  });

  it("hands keyboard focus to the first control once at the top", async () => {
    const root = makeRoot();
    const wrapper = mountButton(root, 1200);
    const btn = wrapper.get("button");
    (btn.element as HTMLElement).focus();
    await btn.trigger("click");
    const first = root.querySelector(".first");
    expect(document.activeElement).not.toBe(first);

    await wrapper.setProps({ scrollTop: 300 });
    expect(document.activeElement).not.toBe(first);
    await wrapper.setProps({ scrollTop: 0 });
    expect(document.activeElement).toBe(first);
  });

  it("drops the handoff when the scroll stops short of the top", async () => {
    const root = makeRoot();
    const wrapper = mountButton(root, 1200);
    const btn = wrapper.get("button");
    (btn.element as HTMLElement).focus();
    await btn.trigger("click");
    setPageScroll(500);
    document.dispatchEvent(new Event("scrollend"));

    await wrapper.setProps({ scrollTop: 0 });
    expect(document.activeElement).not.toBe(root.querySelector(".first"));
  });

  it("drops the handoff when focus moves elsewhere mid-scroll", async () => {
    const root = makeRoot();
    const other = document.createElement("button");
    document.body.appendChild(other);
    const wrapper = mountButton(root, 1200);
    const btn = wrapper.get("button");
    (btn.element as HTMLElement).focus();
    await btn.trigger("click");
    other.focus();

    await wrapper.setProps({ scrollTop: 0 });
    expect(document.activeElement).toBe(other);
  });

  it("leaves focus alone on a pointer click", async () => {
    const root = makeRoot();
    const wrapper = mountButton(root, 1200);
    await wrapper.get("button").trigger("click");
    await wrapper.setProps({ scrollTop: 0 });
    expect(document.activeElement).not.toBe(root.querySelector(".first"));
  });
});
