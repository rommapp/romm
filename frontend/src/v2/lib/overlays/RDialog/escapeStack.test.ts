import { afterEach, describe, expect, it, vi } from "vitest";
import {
  type EscapableEntry,
  isUnderOpenEscapable,
  onEscapableOpen,
  popEscapable,
  pushEscapable,
} from "./escapeStack";

function entry(panel?: HTMLElement): EscapableEntry {
  return { close: () => {}, persistent: false, panel: panel && (() => panel) };
}

const open: EscapableEntry[] = [];
function push(e: EscapableEntry) {
  open.push(e);
  pushEscapable(e);
}

afterEach(() => {
  for (const e of open.splice(0)) popEscapable(e);
});

describe("onEscapableOpen", () => {
  it("notifies subscribers on every push until they unsubscribe", () => {
    const listener = vi.fn();
    const stop = onEscapableOpen(listener);

    push(entry());
    push(entry());
    expect(listener).toHaveBeenCalledTimes(2);

    stop();
    push(entry());
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("does not notify on pop", () => {
    const listener = vi.fn();
    const stop = onEscapableOpen(listener);
    const e = entry();

    push(e);
    popEscapable(e);
    open.splice(open.indexOf(e), 1);
    expect(listener).toHaveBeenCalledTimes(1);

    stop();
  });
});

describe("isUnderOpenEscapable", () => {
  it("is false when nothing is open", () => {
    expect(isUnderOpenEscapable(document.createElement("div"))).toBe(false);
  });

  it("covers a node outside the topmost panel but not one inside it", () => {
    const panel = document.createElement("div");
    const inside = panel.appendChild(document.createElement("button"));
    const outside = document.createElement("button");
    push(entry(panel));

    expect(isUnderOpenEscapable(outside)).toBe(true);
    expect(isUnderOpenEscapable(inside)).toBe(false);
  });

  it("judges against the topmost panel only, so an outer overlay's own content counts as covered", () => {
    const outer = document.createElement("div");
    const inOuter = outer.appendChild(document.createElement("button"));
    const inner = document.createElement("div");
    push(entry(outer));
    expect(isUnderOpenEscapable(inOuter)).toBe(false);

    push(entry(inner));
    expect(isUnderOpenEscapable(inOuter)).toBe(true);
  });

  it("covers nothing while an entry with no panel is on top", () => {
    push(entry(document.createElement("div")));
    push(entry());

    expect(isUnderOpenEscapable(document.createElement("button"))).toBe(false);
  });

  it("treats a missing node as covered", () => {
    push(entry(document.createElement("div")));

    expect(isUnderOpenEscapable(null)).toBe(true);
  });
});
