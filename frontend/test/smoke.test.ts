import { describe, expect, it } from "vitest";

describe("vitest harness", () => {
  it("provides a DOM via happy-dom", () => {
    expect(typeof window).toBe("object");
    expect(typeof document).toBe("object");
  });

  it("can resolve the @ alias", async () => {
    const mod = await import("@/locales");
    expect(mod).toBeDefined();
  });

  it("can resolve the @v2 alias", async () => {
    const tokens = await import("@v2/tokens");
    expect(tokens).toBeDefined();
  });
});
