import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import PasswordField from "./PasswordField.vue";

vi.mock("vue-i18n");

const RTextField = {
  props: { type: { type: String, default: "text" } },
  emits: ["click:append-inner"],
  template: `<button class="field" :data-type="type" @click="$emit('click:append-inner')" />`,
};

describe("PasswordField reveal", () => {
  let frames: FrameRequestCallback[] = [];

  function step() {
    const pending = frames;
    frames = [];
    pending.forEach((cb) => cb(0));
  }

  beforeEach(() => {
    vi.useFakeTimers();
    frames = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });
  });

  async function toggle() {
    const wrapper = mount(PasswordField, {
      global: { stubs: { RTextField } },
    });
    await wrapper.get(".field").trigger("click");
    step();
    step();
    await nextTick();
    return wrapper;
  }

  it("swaps the input type at the blur peak and ends the reveal after", async () => {
    const wrapper = await toggle();
    const field = () => wrapper.get(".field");
    expect(field().classes()).toContain("r-password-field--revealing");
    expect(field().attributes("data-type")).toBe("password");

    vi.advanceTimersByTime(110);
    await nextTick();
    expect(field().attributes("data-type")).toBe("text");
    expect(field().classes()).toContain("r-password-field--revealing");

    vi.advanceTimersByTime(130);
    await nextTick();
    expect(field().classes()).not.toContain("r-password-field--revealing");
  });

  it("drops the pending swap on unmount", async () => {
    const wrapper = await toggle();
    expect(vi.getTimerCount()).toBe(2);

    wrapper.unmount();

    expect(vi.getTimerCount()).toBe(0);
  });
});
