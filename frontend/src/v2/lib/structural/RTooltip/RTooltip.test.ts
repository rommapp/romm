/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import RTooltip from "./RTooltip.vue";

describe("RTooltip", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("anchors to the activator a `v-if` swapped in", async () => {
    const panel = document.createElement("div");
    document.body.append(panel);
    const swapped = ref(false);
    const Host = defineComponent({
      components: { RTooltip },
      setup: () => ({ swapped }),
      template: `
        <RTooltip text="Tip" :open-delay="0">
          <template #activator="{ props }">
            <button v-if="!swapped" type="button" class="a" v-bind="props">A</button>
            <button v-else type="button" class="b" v-bind="props">B</button>
          </template>
        </RTooltip>`,
    });
    const wrapper = mount(Host, { attachTo: panel });
    const dialog: EscapableEntry = {
      close: vi.fn(),
      persistent: false,
      panel: () => panel,
    };
    pushEscapable(dialog);
    swapped.value = true;
    await nextTick();

    await wrapper
      .get("button.b")
      .trigger("pointerenter", { pointerType: "mouse" });
    await flushPromises();

    expect(document.querySelector(".r-tooltip")).not.toBeNull();
    popEscapable(dialog);
    wrapper.unmount();
  });
});

describe("RTooltip reveal timing", () => {
  beforeEach(() =>
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }),
  );
  afterEach(() => {
    document.body.innerHTML = "";
  });

  const tip = () => document.querySelector(".r-tooltip");

  function mountSlot(attrs = "") {
    return mount(
      defineComponent({
        components: { RTooltip },
        template: `
          <RTooltip text="Tip" ${attrs}>
            <template #activator="{ props }">
              <button type="button" v-bind="props">A</button>
            </template>
          </RTooltip>`,
      }),
      { attachTo: document.body },
    );
  }

  async function hover(wrapper: ReturnType<typeof mountSlot>, type: string) {
    await wrapper.get("button").trigger(type, { pointerType: "mouse" });
  }

  it("opens once the pointer has rested for the open delay", async () => {
    const wrapper = mountSlot(':open-delay="300"');

    await hover(wrapper, "pointerenter");
    await vi.advanceTimersByTimeAsync(299);
    expect(tip()).toBeNull();

    await vi.advanceTimersByTimeAsync(1);
    expect(tip()).not.toBeNull();
  });

  it("drops a pending open when the pointer leaves first", async () => {
    const wrapper = mountSlot(':open-delay="300"');

    await hover(wrapper, "pointerenter");
    await vi.advanceTimersByTimeAsync(200);
    await hover(wrapper, "pointerleave");
    await vi.advanceTimersByTimeAsync(500);

    expect(tip()).toBeNull();
  });

  it("closes after the close delay, and a return cancels it", async () => {
    const wrapper = mountSlot(':open-delay="0" :close-delay="200"');
    await hover(wrapper, "pointerenter");
    expect(tip()).not.toBeNull();

    await hover(wrapper, "pointerleave");
    await vi.advanceTimersByTimeAsync(100);
    await hover(wrapper, "pointerenter");
    await vi.advanceTimersByTimeAsync(500);
    expect(tip()).not.toBeNull();

    await hover(wrapper, "pointerleave");
    await vi.advanceTimersByTimeAsync(200);
    expect(tip()).toBeNull();
  });

  it("ignores a touch that passes over the activator", async () => {
    const wrapper = mountSlot(':open-delay="0"');

    await wrapper
      .get("button")
      .trigger("pointerenter", { pointerType: "touch" });

    expect(tip()).toBeNull();
  });

  it("drops a pending open when it unmounts", async () => {
    const wrapper = mountSlot(':open-delay="300"');
    await hover(wrapper, "pointerenter");

    wrapper.unmount();

    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("RTooltip on its parent", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  const show = ref(true);
  const Host = defineComponent({
    components: { RTooltip },
    setup: () => ({ show }),
    template: `
      <span class="parent">
        Badge
        <RTooltip v-if="show" activator="parent" text="Tip" :open-delay="0" />
      </span>`,
  });

  afterEach(() => {
    show.value = true;
  });

  it("reveals on the parent's hover and hides on its leave", async () => {
    const wrapper = mount(Host, { attachTo: document.body });
    await nextTick();
    const parent = wrapper.get(".parent");

    await parent.trigger("pointerenter", { pointerType: "mouse" });
    expect(document.querySelector(".r-tooltip")).not.toBeNull();

    await parent.trigger("pointerleave", { pointerType: "mouse" });
    expect(document.querySelector(".r-tooltip")).toBeNull();
  });

  it("lets go of the parent's listeners once removed", async () => {
    const wrapper = mount(Host, { attachTo: document.body });
    await nextTick();
    const remove = vi.spyOn(
      wrapper.get(".parent").element,
      "removeEventListener",
    );

    show.value = false;
    await nextTick();

    expect(remove.mock.calls.map(([event]) => event).sort()).toEqual([
      "click",
      "focusin",
      "focusout",
      "pointerdown",
      "pointerenter",
      "pointerleave",
    ]);
  });
});

describe("RTooltip opened by a tap", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("toggles on a tap and closes on a tap elsewhere", async () => {
    const outside = document.createElement("div");
    document.body.append(outside);
    const wrapper = mount(
      defineComponent({
        components: { RTooltip },
        template: `
          <RTooltip text="Tip" open-on-tap>
            <template #activator="{ props }">
              <button type="button" v-bind="props">i</button>
            </template>
          </RTooltip>`,
      }),
      { attachTo: document.body },
    );
    const button = wrapper.get("button");

    await button.trigger("pointerdown", { pointerType: "touch" });
    await button.trigger("click");
    await nextTick();
    expect(document.querySelector(".r-tooltip")).not.toBeNull();

    button.element.dispatchEvent(
      new PointerEvent("pointerdown", { bubbles: true }),
    );
    await nextTick();
    expect(document.querySelector(".r-tooltip")).not.toBeNull();

    outside.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
    await nextTick();
    expect(document.querySelector(".r-tooltip")).toBeNull();
  });
});
