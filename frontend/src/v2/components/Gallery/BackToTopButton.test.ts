import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import BackToTopButton from "./BackToTopButton.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const reducedMotion = { value: false };
vi.mock("@/v2/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: reducedMotion }),
}));

function makeScroller(clientHeight = 800) {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientHeight", { value: clientHeight });
  el.scrollTo = vi.fn() as typeof el.scrollTo;
  const first = document.createElement("button");
  first.className = "first";
  el.appendChild(first);
  document.body.appendChild(el);
  return el;
}

function mountButton(scroller: HTMLElement, scrollTop: number) {
  return mount(BackToTopButton, {
    attachTo: document.body,
    props: { scroller, scrollTop },
    global: { stubs: { transition: false } },
  });
}

afterEach(() => {
  document.body.innerHTML = "";
  reducedMotion.value = false;
});

describe("BackToTopButton", () => {
  it("stays hidden within the first viewport", () => {
    const wrapper = mountButton(makeScroller(), 400);
    expect(wrapper.find("button").exists()).toBe(false);
  });

  it("shows once scrolled past a viewport", async () => {
    const wrapper = mountButton(makeScroller(), 400);
    await wrapper.setProps({ scrollTop: 1200 });
    expect(wrapper.get("button").attributes("aria-label")).toBe(
      "gallery.back-to-top",
    );
  });

  it("smooth-scrolls the scroller to the top and emits", async () => {
    const scroller = makeScroller();
    const wrapper = mountButton(scroller, 1200);
    await wrapper.get("button").trigger("click");
    expect(scroller.scrollTo).toHaveBeenCalledWith({
      top: 0,
      behavior: "smooth",
    });
    expect(wrapper.emitted("scroll-to-top")).toHaveLength(1);
  });

  it("jumps without animation under reduced motion", async () => {
    reducedMotion.value = true;
    const scroller = makeScroller();
    const wrapper = mountButton(scroller, 1200);
    await wrapper.get("button").trigger("click");
    expect(scroller.scrollTo).toHaveBeenCalledWith({
      top: 0,
      behavior: "auto",
    });
  });

  it("hands keyboard focus to the first control at the top", async () => {
    const scroller = makeScroller();
    const wrapper = mountButton(scroller, 1200);
    const btn = wrapper.get("button");
    (btn.element as HTMLElement).focus();
    await btn.trigger("click");
    expect(document.activeElement).toBe(scroller.querySelector(".first"));
  });

  it("leaves focus alone on a pointer click", async () => {
    const scroller = makeScroller();
    const wrapper = mountButton(scroller, 1200);
    await wrapper.get("button").trigger("click");
    expect(document.activeElement).not.toBe(scroller.querySelector(".first"));
  });
});
