import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { gamepadFixture } from "@/utils/gamepad.fixtures";
import RBox3D from "./RBox3D.vue";

describe("RBox3D", () => {
  let frame: FrameRequestCallback | null = null;
  let now = 0;

  function step() {
    const pending = frame;
    frame = null;
    pending?.(now);
  }

  beforeEach(() => {
    frame = null;
    now = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frame = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frame = null;
    });
    vi.spyOn(performance, "now").mockImplementation(() => now);
    HTMLElement.prototype.setPointerCapture ??= () => {};
  });

  // The root's listeners bind once the template ref has settled.
  async function render(autoSpin = false) {
    const wrapper = mount(RBox3D, {
      props: { front: "f.png", back: "b.png", spine: "s.png", autoSpin },
    });
    await nextTick();
    return wrapper;
  }

  const yaw = (wrapper: Awaited<ReturnType<typeof render>>) =>
    wrapper.get(".r-box3d__box").attributes("style");

  it.each([
    { connected: true, turns: true },
    { connected: false, turns: false },
  ])(
    "reads the right stick while focused (pad connected: $connected)",
    async ({ connected, turns }) => {
      const pad = { ...gamepadFixture({ axes: [0, 0, 1, 0] }), connected };
      Object.defineProperty(navigator, "getGamepads", {
        value: () => [pad],
        configurable: true,
      });
      const wrapper = mount(RBox3D, {
        props: { front: "f.png", back: "b.png", spine: "s.png" },
        attachTo: document.body,
      });
      await nextTick();
      (wrapper.element as HTMLElement).focus();
      const before = yaw(wrapper);

      step();
      await nextTick();

      expect(yaw(wrapper) !== before).toBe(turns);
      wrapper.unmount();
    },
  );

  it("turns with the arrow keys", async () => {
    const wrapper = await render();

    await wrapper.trigger("keydown", { key: "ArrowRight" });

    expect(yaw(wrapper)).toContain("rotateY(46deg)");
  });

  it("turns with a pointer drag", async () => {
    const wrapper = await render();

    await wrapper.trigger("pointerdown", { pointerId: 1, clientX: 0 });
    await wrapper.trigger("pointermove", { pointerId: 1, clientX: 100 });
    // A release well after the last move carries no flick.
    now = 500;
    await wrapper.trigger("pointerup", { pointerId: 1, clientX: 100 });

    expect(yaw(wrapper)).toContain("rotateY(77deg)");
  });

  it("coasts on after a flick", async () => {
    const wrapper = await render();

    await wrapper.trigger("pointerdown", { pointerId: 1, clientX: 0 });
    await wrapper.trigger("pointermove", { pointerId: 1, clientX: 10 });
    await wrapper.trigger("pointerup", { pointerId: 1, clientX: 10 });

    expect(yaw(wrapper)).toContain("rotateY(90.5deg)");
  });

  it("ends a drag when the pointer is cancelled", async () => {
    const wrapper = await render();

    await wrapper.trigger("pointerdown", { pointerId: 1, clientX: 0 });
    now = 500;
    await wrapper.trigger("pointercancel", { pointerId: 1, clientX: 0 });
    await wrapper.trigger("pointermove", { pointerId: 1, clientX: 100 });

    expect(yaw(wrapper)).toContain("rotateY(32deg)");
  });

  it("drifts once it has been left alone", async () => {
    const wrapper = await render(true);
    now = 5000;

    step();
    await wrapper.vm.$nextTick();

    expect(yaw(wrapper)).toContain("rotateY(32.18deg)");
  });

  it("stops its frame loop once unmounted", async () => {
    const wrapper = await render();
    expect(frame).not.toBeNull();

    wrapper.unmount();

    expect(frame).toBeNull();
  });
});
