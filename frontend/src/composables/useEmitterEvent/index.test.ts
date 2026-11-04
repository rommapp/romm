import { mount } from "@vue/test-utils";
import mitt from "mitt";
import { describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { Events } from "@/types/emitter";
import { type EmitterEventHandle, useEmitterEvent } from "./index";

function mountListener(
  emitter: ReturnType<typeof mitt<Events>>,
  handler: () => void,
) {
  let handle: EmitterEventHandle | undefined;
  const wrapper = mount(
    defineComponent({
      setup() {
        handle = useEmitterEvent("showAboutDialog", handler);
        return () => null;
      },
    }),
    { global: { provide: { emitter } } },
  );
  return { wrapper, stop: () => handle?.stop() };
}

describe("useEmitterEvent", () => {
  it("unsubscribes when the component unmounts", () => {
    const emitter = mitt<Events>();
    const handler = vi.fn();
    const { wrapper } = mountListener(emitter, handler);

    emitter.emit("showAboutDialog", null);
    expect(handler).toHaveBeenCalledTimes(1);

    wrapper.unmount();
    emitter.emit("showAboutDialog", null);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not stack handlers across remounts", () => {
    const emitter = mitt<Events>();
    const handler = vi.fn();
    mountListener(emitter, handler).wrapper.unmount();
    mountListener(emitter, handler).wrapper.unmount();
    mountListener(emitter, handler);

    emitter.emit("showAboutDialog", null);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("stops early and stays stopped", () => {
    const emitter = mitt<Events>();
    const handler = vi.fn();
    const { wrapper, stop } = mountListener(emitter, handler);

    stop();
    stop();
    emitter.emit("showAboutDialog", null);
    expect(handler).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
