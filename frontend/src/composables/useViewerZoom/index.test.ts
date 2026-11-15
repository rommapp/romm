import { beforeEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import { useViewerZoom } from "./index";

beforeEach(() => localStorage.clear());

describe("useViewerZoom", () => {
  it("steps through the zoom levels and stops at either end", () => {
    const { zoom, zoomIn, zoomOut, canZoomIn, canZoomOut } = useViewerZoom(
      "test.fit",
      "page",
    );

    expect(zoomIn()).toBe(true);
    expect(zoom.value).toBe(1.25);

    while (zoomIn());
    expect(zoom.value).toBe(4);
    expect(canZoomIn.value).toBe(false);

    while (zoomOut());
    expect(zoom.value).toBe(0.5);
    expect(canZoomOut.value).toBe(false);
  });

  it("steps from an off-step zoom to the nearest step past it", () => {
    const { zoom, zoomIn, zoomOut } = useViewerZoom("test.fit", "page");

    zoom.value = 1.1;
    zoomIn();
    expect(zoom.value).toBe(1.25);

    zoom.value = 1.1;
    zoomOut();
    expect(zoom.value).toBe(1);
  });

  it("toggles the fit back to the fitted size and remembers it", async () => {
    const first = useViewerZoom("test.fit", "page");
    first.zoomIn();

    first.toggleFit();

    expect(first.fit.value).toBe("width");
    expect(first.zoom.value).toBe(1);
    await nextTick();
    expect(useViewerZoom("test.fit", "page").fit.value).toBe("width");
  });
});
