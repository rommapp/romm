import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import MediaShelf, {
  type MediaShelfItem,
} from "@/components/GameDetails/MediaShelf.vue";

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

// jsdom's load() is unimplemented and logs an error.
function stubLoad() {
  return vi
    .spyOn(HTMLMediaElement.prototype, "load")
    .mockImplementation(() => undefined);
}

describe("MediaShelf", () => {
  it("does not start loading a clip until it is played", () => {
    const wrapper = mountShelf([clip]);

    expect(wrapper.get("video").attributes("preload")).toBe("none");
  });

  it("drops the clip source when the shelf unmounts", () => {
    const load = stubLoad();
    const wrapper = mountShelf([clip]);
    const video = wrapper.get("video").element;
    expect(video.getAttribute("src")).toBe(clip.url);

    wrapper.unmount();

    expect(video.hasAttribute("src")).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("drops the clip source when the clip leaves the shelf", async () => {
    const load = stubLoad();
    const wrapper = mountShelf([shot, clip]);
    const video = wrapper.get("video").element;

    await wrapper.setProps({ items: [shot] });

    expect(video.hasAttribute("src")).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("stops the clip played before when another clip plays", async () => {
    const other = { ...clip, key: "other", url: `${clip.url}?other` };
    const wrapper = mountShelf([clip, other]);
    const [first, second] = wrapper
      .findAll("video")
      .map((video) => video.element as HTMLVideoElement);
    const loadFirst = vi
      .spyOn(first!, "load")
      .mockImplementation(() => undefined);
    const loadSecond = vi
      .spyOn(second!, "load")
      .mockImplementation(() => undefined);

    first!.dispatchEvent(new Event("play"));
    expect(loadFirst).not.toHaveBeenCalled();
    second!.dispatchEvent(new Event("play"));
    await nextTick();

    expect(loadFirst).toHaveBeenCalled();
    expect(first!.hasAttribute("src")).toBe(false);
    expect(loadSecond).not.toHaveBeenCalled();
    // A fresh element takes its place, ready to play on demand.
    const fresh = wrapper.findAll("video")[0]!.element;
    expect(fresh).not.toBe(first);
    expect(fresh.getAttribute("src")).toBe(clip.url);
    expect(wrapper.findAll("video")[1]!.element).toBe(second);
  });

  it("keeps a clip's box at the shape it had before play", () => {
    const wrapper = mountShelf([{ ...clip, poster: "/title.png" }]);
    const video = wrapper.get("video").element as HTMLVideoElement;
    const box = vi.spyOn(video, "getBoundingClientRect");

    box.mockReturnValue(new DOMRect(0, 0, 265.14, 232));
    video.dispatchEvent(new Event("play"));
    // The clip's own shape lands with its metadata.
    box.mockReturnValue(new DOMRect(0, 0, 309.33, 232));
    video.dispatchEvent(new Event("play"));

    expect(video.style.aspectRatio).toBe("265.14 / 232");
  });

  it("leaves the box free when its width is held at the cap", () => {
    const wrapper = mountShelf([{ ...clip, poster: "/title.png" }]);
    const video = wrapper.get("video").element as HTMLVideoElement;
    vi.spyOn(video, "getBoundingClientRect").mockReturnValue(
      new DOMRect(0, 0, 256, 168),
    );
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      maxWidth: "256px",
    } as CSSStyleDeclaration);

    video.dispatchEvent(new Event("play"));

    expect(video.style.aspectRatio).toBe("");
  });
});
