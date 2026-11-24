import { describe, expect, it } from "vitest";
import { consoleKindOf } from "@/utils/consoles";

describe("consoleKindOf", () => {
  it("names the console a client registers as", () => {
    expect(consoleKindOf("ps3")).toBe("ps3");
    expect(consoleKindOf("ps4")).toBe("ps4");
  });

  it("is null for other clients", () => {
    expect(consoleKindOf("retroarch")).toBeNull();
    expect(consoleKindOf("toString")).toBeNull();
    expect(consoleKindOf(null)).toBeNull();
  });
});
