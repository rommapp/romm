import { enableAutoUnmount, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import StreamStage from "./StreamStage.vue";

// The stage listens on window and runs attach timers, so a mount left standing
// would answer the next test's events.
enableAutoUnmount(afterEach);

function mountStage(src: string) {
  return mount(StreamStage, {
    props: { src, frameTitle: "Stream" },
    global: { stubs: { teleport: true } },
  });
}

function frameAttr(name: string): string {
  return (
    mountStage("http://box:3010/room").find("iframe").attributes(name) ?? ""
  );
}

describe("StreamStage", () => {
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
    expect(frameAttr("sandbox")).not.toContain("allow-top-navigation");
  });

  it.each([
    "gamepad",
    "fullscreen",
    "autoplay",
    "camera",
    "microphone",
    "clipboard-write",
  ])("delegates %s to the container", (feature) => {
    const directives = frameAttr("allow")
      .split(";")
      .map((d) => d.trim());
    expect(directives).toContain(`${feature} *`);
  });

  // An opaque origin gets no media permission, so the room's webcam and mic
  // need the container to keep its own origin.
  it.each(["allow-scripts", "allow-same-origin"])(
    "keeps %s so the room can run and ask for media",
    (flag) => {
      expect(frameAttr("sandbox").split(/\s+/)).toContain(flag);
    },
  );
});
