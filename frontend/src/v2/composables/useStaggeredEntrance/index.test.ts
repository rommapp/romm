import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { useStaggeredEntrance } from "./index";

type Row = ReturnType<typeof useStaggeredEntrance>;

/** A row whose root sits at `slot` among `container`'s children. */
function rowAt(container: HTMLElement, slot: number, ready?: () => boolean) {
  const el = document.createElement("a");
  container.insertBefore(el, container.children[slot] ?? null);
  return useStaggeredEntrance(ref(el), ready);
}

function list(): HTMLElement {
  const container = document.createElement("div");
  document.body.appendChild(container);
  return container;
}

/** The stagger slot a row was given, as its style hands it to the CSS. */
function slot(row: Row): number {
  return row.entranceStyle.value["--asset-fade-i"];
}

function fading(row: Row): boolean {
  return row.entranceClass.value["r-v2-asset-fade"];
}

/** Lets the tick's arrivals settle into their ranks. */
async function settle() {
  await Promise.resolve();
  await nextTick();
}

describe("useStaggeredEntrance", () => {
  it("plays the entrance on a row that mounts with its content", async () => {
    const row = rowAt(list(), 0);
    await settle();

    expect(fading(row)).toBe(true);
    expect(slot(row)).toBe(0);
  });

  // Vue mounts a keyed batch bottom-up; the cascade still runs top-down.
  it("cascades a batch in the order it sits on screen", async () => {
    const container = list();
    const third = rowAt(container, 0);
    const second = rowAt(container, 0);
    const first = rowAt(container, 0);
    await settle();

    expect([first, second, third].map(slot)).toEqual([0, 1, 2]);
  });

  it("starts a lone later arrival without a delay", async () => {
    const container = list();
    rowAt(container, 0);
    rowAt(container, 1);
    await settle();

    const late = rowAt(container, 2);
    await settle();

    expect(slot(late)).toBe(0);
  });

  it("stops lengthening the cascade past the rows a screen holds", async () => {
    const container = list();
    const rows = Array.from({ length: 20 }, (_, i) => rowAt(container, i));
    await settle();

    expect(slot(rows[19])).toBe(12);
  });

  it("waits for the row's content before playing", async () => {
    const ready = ref(false);
    const row = rowAt(list(), 0, () => ready.value);

    expect(fading(row)).toBe(false);

    ready.value = true;
    await settle();

    expect(fading(row)).toBe(true);
  });

  // A re-sort re-inserts keyed rows, which would restart a class still set.
  it("drops the class once the entrance has played", async () => {
    const row = rowAt(list(), 0);
    await settle();

    row.endEntrance();

    expect(fading(row)).toBe(false);
  });
});
