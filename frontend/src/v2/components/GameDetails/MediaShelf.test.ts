import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import MediaShelf, {
  type MediaShelfItem,
} from "@/v2/components/GameDetails/MediaShelf.vue";

vi.mock("vue-i18n");

const clip: MediaShelfItem = {
  key: "video",
  label: "Trailer",
  url: "/assets/romm/resources/roms/1/2/video/video.mp4",
  isVideo: true,
};
const shot: MediaShelfItem = {
  key: "shot",
  label: "Screenshot",
  url: "/assets/romm/resources/roms/1/2/screenshots/0.png",
};

function mountShelf(items: MediaShelfItem[]) {
  return mount(MediaShelf, {
    props: { items },
    global: { stubs: { RCarousel: true, RIcon: true } },
  });
}

describe("MediaShelf", () => {
  it("does not start loading a clip until it is played", () => {
    const wrapper = mountShelf([clip]);

    expect(wrapper.get("video").attributes("preload")).toBe("none");
  });

  it("drops the clip source when the shelf unmounts", () => {
    const load = vi
      .spyOn(HTMLMediaElement.prototype, "load")
      .mockImplementation(() => undefined);
    const wrapper = mountShelf([clip]);
    const video = wrapper.get("video").element;
    expect(video.getAttribute("src")).toBe(clip.url);

    wrapper.unmount();

    expect(video.hasAttribute("src")).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("drops the clip source when the clip leaves the shelf", async () => {
    const load = vi
      .spyOn(HTMLMediaElement.prototype, "load")
      .mockImplementation(() => undefined);
    const wrapper = mountShelf([shot, clip]);
    const video = wrapper.get("video").element;

    await wrapper.setProps({ items: [shot] });

    expect(video.hasAttribute("src")).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });
});
