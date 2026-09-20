import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { rom } from "@/v2/components/Gallery/listRowFixture";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import { edgeSpeed, useGallerySelectionInput } from "./index";

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

/** A move of the finger already tracked by the press. */
function move(clientX: number, clientY: number): PointerEvent {
  return new PointerEvent("pointermove", {
    pointerType: "touch",
    isPrimary: true,
    clientX,
    clientY,
  });
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

  // Dragging on from the press selects what it crosses, and crossing the
  // same row twice must not flip it back off.
  it("paints the rows the drag crosses", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    row.dataset.romPosition = "0";
    const next = document.createElement("a");
    next.dataset.romPosition = "1";
    document.body.append(row, next);
    vi.spyOn(document, "elementFromPoint").mockReturnValue(next);
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockReturnValue(rom({ id: 2 }));

    input.handlePointerDown(rom({ id: 1 }), 0, pressOn(row));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    input.handlePointerMove(move(20, 40));
    input.handlePointerMove(move(21, 41));

    expect(storeGallerySelection().count).toBe(2);
    row.remove();
    next.remove();
  });

  it("paints nothing until the press has turned into a long one", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    const next = document.createElement("a");
    next.dataset.romPosition = "1";
    vi.spyOn(document, "elementFromPoint").mockReturnValue(next);

    input.handlePointerDown(rom({ id: 1 }), 0, pressOn(row));
    input.handlePointerMove(move(200, 400));
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

describe("edgeSpeed", () => {
  const TOP = 100;
  const BOTTOM = 700;

  it("stays still away from both edges", () => {
    expect(edgeSpeed(400, TOP, BOTTOM)).toBe(0);
  });

  it("pulls up near the top and down near the bottom", () => {
    expect(edgeSpeed(TOP + 10, TOP, BOTTOM)).toBeLessThan(0);
    expect(edgeSpeed(BOTTOM - 10, TOP, BOTTOM)).toBeGreaterThan(0);
  });

  // Deeper into the band means faster, so a finger parked at the very edge
  // pulls hardest and one just inside it barely moves.
  it("speeds up the deeper into the band the finger goes", () => {
    const shallow = edgeSpeed(BOTTOM - 60, TOP, BOTTOM);
    const deep = edgeSpeed(BOTTOM - 5, TOP, BOTTOM);

    expect(deep).toBeGreaterThan(shallow);
    expect(shallow).toBeGreaterThan(0);
  });

  it("caps the pull past the edge", () => {
    expect(edgeSpeed(BOTTOM + 500, TOP, BOTTOM)).toBe(
      edgeSpeed(BOTTOM, TOP, BOTTOM),
    );
  });
});
