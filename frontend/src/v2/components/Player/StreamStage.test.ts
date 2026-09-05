import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StreamStage from "./StreamStage.vue";

function mountStage(src: string) {
  return mount(StreamStage, {
    props: { src, frameTitle: "Stream" },
    global: { stubs: { teleport: true } },
  });
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
    const sandbox = mountStage("http://box:3010/room")
      .find("iframe")
      .attributes("sandbox");
    expect(sandbox).not.toContain("allow-top-navigation");
  });
});
