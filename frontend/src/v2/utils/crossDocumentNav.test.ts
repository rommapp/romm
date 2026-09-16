import { afterEach, describe, expect, it, vi } from "vitest";
import { armCrossDocumentTransition } from "./crossDocumentNav";

// Read back by the parser-blocking script in index.html, which cannot import.
const NAV_KEY = "romm-xdoc-nav";

/** Every opt-in the document is carrying, as the engine would read them. */
function optIns(): string[] {
  return Array.from(document.head.querySelectorAll("style"))
    .map((s) => s.textContent ?? "")
    .filter((text) => text.includes("@view-transition"));
}

describe("armCrossDocumentTransition", () => {
  afterEach(() => {
    sessionStorage.clear();
    document.head.querySelectorAll("style").forEach((s) => s.remove());
    vi.restoreAllMocks();
  });

  it("records the player document the launch is heading to", () => {
    armCrossDocumentTransition("/rom/1/ejs");
    expect(sessionStorage.getItem(NAV_KEY)).toBe("/rom/1/ejs");
  });

  it("records the js-dos player document too", () => {
    armCrossDocumentTransition("/rom/7/jsdos");
    expect(sessionStorage.getItem(NAV_KEY)).toBe("/rom/7/jsdos");
  });

  it("opts this document in so the transition can be performed at all", () => {
    armCrossDocumentTransition("/rom/1/ejs");
    expect(optIns()).toHaveLength(1);
    expect(optIns()[0]).toContain("navigation: auto");
  });

  // Without the marker the player document cannot know to opt in, and a
  // transition with only this end armed is aborted and logs a console error.
  it("does not throw when storage refuses the write, and leaves this end unarmed", () => {
    vi.spyOn(window.sessionStorage, "setItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(() => armCrossDocumentTransition("/rom/1/ejs")).not.toThrow();
    expect(optIns()).toHaveLength(0);
  });
});
