import { mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { useNavGlass } from "@/v2/composables/useNavGlass";
import { usePinnedToolbar } from "./index";

const NAV_H = 58;
const NATURAL_TOP = 300;

const wrappers: VueWrapper[] = [];

function setup() {
  const scrollTop = ref(0);
  let api!: ReturnType<typeof usePinnedToolbar>;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = usePinnedToolbar(scrollTop);
        return () => h("div");
      },
    }),
  );
  wrappers.push(wrapper);
  return { scrollTop, api, wrapper };
}

// A header, the sentinel at the toolbar's natural top, and the sticky toolbar.
function bindShell(api: ReturnType<typeof usePinnedToolbar>) {
  const parent = document.createElement("div");
  const header = document.createElement("div");
  const sentinel = document.createElement("div");
  const toolbar = document.createElement("div");
  toolbar.style.top = `${NAV_H}px`;
  Object.defineProperty(sentinel, "offsetTop", { value: NATURAL_TOP });
  parent.append(header, sentinel, toolbar);
  document.body.append(parent);
  api.bindSentinel(sentinel);
  api.bindToolbar(toolbar);
}

describe("usePinnedToolbar", () => {
  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
    document.body.innerHTML = "";
  });

  it("pins once the scroller reaches the toolbar's natural top", async () => {
    const { scrollTop, api } = setup();
    const { innerScrolled, innerGlass } = useNavGlass();
    bindShell(api);
    expect(api.pinDistance.value).toBe(NATURAL_TOP - NAV_H);

    scrollTop.value = NATURAL_TOP - NAV_H - 1;
    await nextTick();
    expect(api.pinned.value).toBe(false);
    expect(innerScrolled.value).toBe(true);
    expect(innerGlass.value).toBe(false);

    scrollTop.value = NATURAL_TOP - NAV_H;
    await nextTick();
    expect(api.pinned.value).toBe(true);
    expect(innerGlass.value).toBe(true);
  });

  it("never takes the top bar's glass without a toolbar", async () => {
    const { scrollTop, api } = setup();
    const { innerScrolled, innerGlass } = useNavGlass();

    scrollTop.value = 500;
    await nextTick();
    expect(api.pinned.value).toBe(false);
    expect(innerScrolled.value).toBe(true);
    expect(innerGlass.value).toBe(false);
  });

  it("hands the glass back to the top bar on unmount", async () => {
    const { scrollTop, api, wrapper } = setup();
    const { innerScrolled, innerGlass } = useNavGlass();
    bindShell(api);
    scrollTop.value = 1000;
    await nextTick();
    expect(innerGlass.value).toBe(true);

    wrapper.unmount();
    wrappers.splice(wrappers.indexOf(wrapper), 1);
    expect(innerScrolled.value).toBe(false);
    expect(innerGlass.value).toBe(false);
  });
});
