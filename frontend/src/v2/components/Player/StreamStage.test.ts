import { mount } from "@vue/test-utils";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import StreamStage from "./StreamStage.vue";

function mountStage(src: string) {
  return mount(StreamStage, {
    props: { src, frameTitle: "Stream" },
    global: { stubs: { teleport: true } },
  });
}

describe("StreamStage", () => {
  let allow: string[] = [];
  let sandbox: string[] = [];
  beforeAll(() => {
    const frame = mountStage("http://box:3010/room").find("iframe");
    allow = (frame.attributes("allow") ?? "").split(";").map((d) => d.trim());
    sandbox = (frame.attributes("sandbox") ?? "").split(/\s+/);
  });

  it("renders a container URL the broker answered with", () => {
    const wrapper = mountStage("http://192.168.1.10:3000/streaming/room/abc");
    expect(wrapper.find("iframe").attributes("src")).toBe(
      "http://192.168.1.10:3000/streaming/room/abc",
    );
  });

  it.each(["javascript:alert(1)", "data:text/html,x"])(
    "refuses to render %s",
    (src) => {
      expect(mountStage(src).find("iframe").exists()).toBe(false);
    },
  );

  it("does not let the container steer the tab it sits in", () => {
    expect(sandbox.join(" ")).not.toContain("allow-top-navigation");
  });

  it.each([
    "gamepad",
    "fullscreen",
    "autoplay",
    "camera",
    "microphone",
    "clipboard-write",
  ])("delegates %s to the container", (feature) => {
    expect(allow).toContain(`${feature} *`);
  });

  // An opaque origin gets no media permission, so the room's webcam and mic
  // need the container to keep its own origin.
  it.each(["allow-scripts", "allow-same-origin"])(
    "keeps %s so the room can run and ask for media",
    (flag) => {
      expect(sandbox).toContain(flag);
    },
  );
});

describe("StreamStage controls bar", () => {
  beforeEach(() =>
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }),
  );

  const barShown = (wrapper: ReturnType<typeof mountStage>) =>
    wrapper.get(".r-v2-stage__bar").classes("r-v2-stage__bar--visible");

  it("hides the bar once the stage has been left alone", async () => {
    const wrapper = mountStage("http://box:3010/room");
    expect(barShown(wrapper)).toBe(true);

    await vi.advanceTimersByTimeAsync(2499);
    expect(barShown(wrapper)).toBe(true);

    await vi.advanceTimersByTimeAsync(1);
    expect(barShown(wrapper)).toBe(false);
  });

  it("restarts the wait when the pointer reaches the top edge", async () => {
    const wrapper = mountStage("http://box:3010/room");
    await vi.advanceTimersByTimeAsync(2000);

    await wrapper.trigger("mousemove", { clientY: 2 });
    await vi.advanceTimersByTimeAsync(2000);
    expect(barShown(wrapper)).toBe(true);

    await vi.advanceTimersByTimeAsync(500);
    expect(barShown(wrapper)).toBe(false);
  });

  it("drops a pending hide when it unmounts", () => {
    const wrapper = mountStage("http://box:3010/room");

    wrapper.unmount();

    expect(vi.getTimerCount()).toBe(0);
  });
});
