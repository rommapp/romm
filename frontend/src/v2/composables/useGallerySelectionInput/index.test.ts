import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { rom } from "@/v2/components/Gallery/listRowFixture";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import { useGallerySelectionInput } from "./index";

const LONG_PRESS_MS = 500;

/** A touch press that starts on `target`, as the row or card would see it. */
function pressOn(target: Element): PointerEvent {
  const event = new PointerEvent("pointerdown", {
    pointerType: "touch",
    isPrimary: true,
    bubbles: true,
    clientX: 10,
    clientY: 10,
  });
  Object.defineProperty(event, "target", { value: target });
  return event;
}

describe("useGallerySelectionInput long press", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  it("selects the row when the press lands on the row itself", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");

    input.handlePointerDown(rom(), 0, pressOn(row));
    vi.advanceTimersByTime(LONG_PRESS_MS);

    expect(storeGallerySelection().count).toBe(1);
  });

  // Holding a chevron, a kebab or a tick is a press on that control; the row
  // underneath would otherwise select itself behind it.
  it("ignores a press that lands on a nested control", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    const button = document.createElement("button");
    row.appendChild(button);

    input.handlePointerDown(rom(), 0, pressOn(button));
    vi.advanceTimersByTime(LONG_PRESS_MS);

    expect(storeGallerySelection().count).toBe(0);
  });

  it("ignores a press that lands on a tick", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    row.appendChild(checkbox);

    input.handlePointerDown(rom(), 0, pressOn(checkbox));
    vi.advanceTimersByTime(LONG_PRESS_MS);

    expect(storeGallerySelection().count).toBe(0);
  });

  it("leaves the mouse alone", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    const event = new PointerEvent("pointerdown", {
      pointerType: "mouse",
      isPrimary: true,
    });
    Object.defineProperty(event, "target", { value: row });

    input.handlePointerDown(rom(), 0, event);
    vi.advanceTimersByTime(LONG_PRESS_MS);

    expect(storeGallerySelection().count).toBe(0);
  });
});
