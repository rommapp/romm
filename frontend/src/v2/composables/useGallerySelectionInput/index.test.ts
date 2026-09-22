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

/** A bare row element for the press to land on. */
function rowEl(): HTMLElement {
  return document.createElement("a");
}

/** What the drag finds under the finger. happy-dom lays nothing out and has
 *  no `elementsFromPoint`, so the stack is supplied directly. */
function stackAt(...els: Element[]) {
  Object.defineProperty(document, "elementsFromPoint", {
    value: () => els,
    configurable: true,
  });
}

/** A move of the finger already tracked by the press. The press follows it
 *  on the window, so that is where the tests raise it. */
function move(clientX: number, clientY: number): PointerEvent {
  return new PointerEvent("pointermove", {
    pointerType: "touch",
    isPrimary: true,
    clientX,
    clientY,
  });
}

function lift(): PointerEvent {
  return new PointerEvent("pointerup", { pointerType: "touch" });
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

  /** The drag reports the row at `position` as the one under the finger. */
  function overRow(position: number) {
    const el = document.createElement("a");
    el.dataset.romPosition = String(position);
    stackAt(el);
  }

  it("selects the rows the drag reaches", () => {
    const input = useGallerySelectionInput();
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockImplementation((p: number) =>
      rom({ id: 100 + p }),
    );

    input.handlePointerDown(rom({ id: 100 }), 0, pressOn(rowEl()));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    overRow(1);
    window.dispatchEvent(move(20, 40));
    overRow(2);
    window.dispatchEvent(move(20, 60));

    expect(storeGallerySelection().count).toBe(3);
  });

  // Coming back up the list hands back what the drag had taken, so a range
  // can be corrected without lifting the finger.
  it("gives a row back when the drag leaves it behind", () => {
    const input = useGallerySelectionInput();
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockImplementation((p: number) =>
      rom({ id: 100 + p }),
    );

    input.handlePointerDown(rom({ id: 100 }), 0, pressOn(rowEl()));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    overRow(3);
    window.dispatchEvent(move(20, 80));
    overRow(1);
    window.dispatchEvent(move(20, 40));

    expect(storeGallerySelection().count).toBe(2);
  });

  it("leaves a row that was already selected where it was", () => {
    const input = useGallerySelectionInput();
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockImplementation((p: number) =>
      rom({ id: 100 + p }),
    );
    storeGallerySelection().selectMany([rom({ id: 102 })]);

    input.handlePointerDown(rom({ id: 100 }), 0, pressOn(rowEl()));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    overRow(2);
    window.dispatchEvent(move(20, 60));
    overRow(0);
    window.dispatchEvent(move(20, 20));

    // The anchor and the row the user had picked before the drag started.
    expect(storeGallerySelection().isSelected(102)).toBe(true);
    expect(storeGallerySelection().count).toBe(2);
  });

  it("keeps the row the press started on when the drag returns to it", () => {
    const input = useGallerySelectionInput();
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockImplementation((p: number) =>
      rom({ id: 100 + p }),
    );

    input.handlePointerDown(rom({ id: 100 }), 0, pressOn(rowEl()));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    overRow(2);
    window.dispatchEvent(move(20, 60));
    overRow(0);
    window.dispatchEvent(move(20, 20));

    expect(storeGallerySelection().count).toBe(1);
  });

  // The bottom nav and the selection bar cover the list's lower edge, which
  // is where an auto-scrolling drag parks: the row under them still paints.
  it("paints the row under the chrome floating over it", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    const next = document.createElement("a");
    next.dataset.romPosition = "1";
    stackAt(document.createElement("div"), next);
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockReturnValue(rom({ id: 2 }));

    input.handlePointerDown(rom({ id: 1 }), 0, pressOn(row));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    window.dispatchEvent(move(20, 40));

    expect(storeGallerySelection().count).toBe(2);
  });

  it("paints nothing until the press has turned into a long one", () => {
    const input = useGallerySelectionInput();
    const row = document.createElement("a");
    const next = document.createElement("a");
    next.dataset.romPosition = "1";
    stackAt(next);

    input.handlePointerDown(rom({ id: 1 }), 0, pressOn(row));
    window.dispatchEvent(move(200, 400));
    vi.advanceTimersByTime(LONG_PRESS_MS);

    expect(storeGallerySelection().count).toBe(0);
  });

  // The row that took the press is recycled out from under a long drag, and
  // a finger parked at the list's edge sits over the chrome, not over a row:
  // either way the gesture has to keep coming from the window.
  it("keeps painting once the pressed row is gone", () => {
    const input = useGallerySelectionInput();
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockImplementation((p: number) =>
      rom({ id: 100 + p }),
    );
    const row = rowEl();
    document.body.appendChild(row);

    input.handlePointerDown(rom({ id: 100 }), 0, pressOn(row));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    row.remove();
    overRow(1);
    window.dispatchEvent(move(20, 40));

    expect(storeGallerySelection().count).toBe(2);
  });

  it("drops the gesture when the surface goes away under it", () => {
    const input = useGallerySelectionInput();

    input.handlePointerDown(rom(), 0, pressOn(rowEl()));
    input.cancel();
    vi.advanceTimersByTime(LONG_PRESS_MS);

    expect(storeGallerySelection().count).toBe(0);
  });

  // Nothing is left listening for a finger that has already lifted.
  it("stops following the finger once it lifts", () => {
    const input = useGallerySelectionInput();
    vi.spyOn(storeGalleryRoms(), "getRomAt").mockImplementation((p: number) =>
      rom({ id: 100 + p }),
    );

    input.handlePointerDown(rom({ id: 100 }), 0, pressOn(rowEl()));
    vi.advanceTimersByTime(LONG_PRESS_MS);
    window.dispatchEvent(lift());
    overRow(5);
    window.dispatchEvent(move(20, 200));

    expect(storeGallerySelection().count).toBe(1);
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
