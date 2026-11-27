import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RImage from "./RImage.vue";

describe("RImage load event", () => {
  it("emits load for an image another instance already decoded", async () => {
    const src = "/assets/shared-cover.png";
    const first = mount(RImage, { props: { src } });
    await first.get("img").trigger("load");
    expect(first.emitted("load")).toHaveLength(1);

    const second = mount(RImage, { props: { src } });
    await second.get("img").trigger("load");

    expect(second.emitted("load")).toHaveLength(1);
  });

  it("emits load once per src", async () => {
    const wrapper = mount(RImage, { props: { src: "/assets/once.png" } });
    await wrapper.get("img").trigger("load");
    await wrapper.get("img").trigger("load");

    expect(wrapper.emitted("load")).toHaveLength(1);
  });
});
