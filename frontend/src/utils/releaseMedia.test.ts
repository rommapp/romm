import { afterEach, describe, expect, it, vi } from "vitest";
import { claimMedia, claimPreview, releaseMedia } from "@/utils/releaseMedia";

const claimed: HTMLVideoElement[] = [];

function clip() {
  const el = document.createElement("video");
  el.setAttribute("src", "/clip.mp4");
  vi.spyOn(el, "load").mockImplementation(() => undefined);
  claimed.push(el);
  return el;
}

describe("claimMedia", () => {
  afterEach(() => {
    claimed.splice(0).forEach(releaseMedia);
  });

  it("releases the clip played before", () => {
    const first = clip();
    const second = clip();
    const onRelease = vi.fn();

    claimMedia(first, onRelease);
    claimMedia(second, vi.fn());

    expect(first.hasAttribute("src")).toBe(false);
    expect(onRelease).toHaveBeenCalledTimes(1);
    expect(second.getAttribute("src")).toBe("/clip.mp4");
  });

  it("leaves a clip alone when it plays again", () => {
    const first = clip();
    const onRelease = vi.fn();

    claimMedia(first, onRelease);
    claimMedia(first, onRelease);

    expect(onRelease).not.toHaveBeenCalled();
    expect(first.getAttribute("src")).toBe("/clip.mp4");
  });

  it("releases a hover preview when a clip plays", () => {
    const preview = clip();
    const onRelease = vi.fn();

    claimPreview(preview, onRelease);
    claimMedia(clip(), vi.fn());

    expect(preview.hasAttribute("src")).toBe(false);
    expect(onRelease).toHaveBeenCalledTimes(1);
  });

  it("keeps a clip playing when a hover preview starts", () => {
    const playing = clip();
    const onRelease = vi.fn();

    claimMedia(playing, onRelease);
    claimPreview(clip(), vi.fn());

    expect(playing.getAttribute("src")).toBe("/clip.mp4");
    expect(onRelease).not.toHaveBeenCalled();
  });

  it("releases the hover preview played before", () => {
    const first = clip();
    const onRelease = vi.fn();

    claimPreview(first, onRelease);
    claimPreview(clip(), vi.fn());

    expect(first.hasAttribute("src")).toBe(false);
    expect(onRelease).toHaveBeenCalledTimes(1);
  });

  it("forgets a released clip, so the next one has nothing to release", () => {
    const first = clip();
    const onRelease = vi.fn();

    claimMedia(first, onRelease);
    releaseMedia(first);
    claimMedia(clip(), vi.fn());

    expect(onRelease).not.toHaveBeenCalled();
  });
});
