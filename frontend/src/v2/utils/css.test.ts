import { describe, expect, it } from "vitest";
import { toCssUrl } from "./css";

describe("toCssUrl", () => {
  it("wraps urls in quoted css url()", () => {
    expect(toCssUrl("/api/screenshots/state.png")).toBe(
      'url("/api/screenshots/state.png")',
    );
  });

  it("keeps paths with spaces and brackets valid", () => {
    expect(toCssUrl("/api/screenshots/[2026-07-02 03-48-41].png")).toBe(
      'url("/api/screenshots/[2026-07-02 03-48-41].png")',
    );
  });

  it("escapes quotes and backslashes", () => {
    expect(toCssUrl('/api/screenshots/"a"\\b.png')).toBe(
      'url("/api/screenshots/\\"a\\"\\\\b.png")',
    );
  });
});
