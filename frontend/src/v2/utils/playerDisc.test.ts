import { describe, expect, it } from "vitest";
import { resolveStoredDisc } from "./playerDisc";

// Only `id` is read off each file; minimal stubs stand in for RomFileSchema.
const files = (...ids: number[]) => ids.map((id) => ({ id }));

describe("resolveStoredDisc", () => {
  it("keeps a stored id that still belongs to the rom", () => {
    expect(resolveStoredDisc("2", files(1, 2, 3))).toEqual({
      discId: 2,
      stale: false,
    });
  });

  it("falls back to the first file and marks stale when the id is gone", () => {
    // Classic post-rescan case: files were reimported with new ids.
    expect(resolveStoredDisc("2", files(10, 11, 12))).toEqual({
      discId: 10,
      stale: true,
    });
  });

  it("falls back to the first file without staleness when nothing was stored", () => {
    expect(resolveStoredDisc(null, files(5, 6))).toEqual({
      discId: 5,
      stale: false,
    });
  });

  it("treats a non-numeric stored value as stale garbage to forget", () => {
    expect(resolveStoredDisc("not-a-number", files(1))).toEqual({
      discId: 1,
      stale: true,
    });
  });

  it("returns a null disc id (and no staleness) for a rom with no files", () => {
    expect(resolveStoredDisc(null, [])).toEqual({
      discId: null,
      stale: false,
    });
  });

  it("still clears a stored id when the rom now has no files", () => {
    expect(resolveStoredDisc("2", [])).toEqual({
      discId: null,
      stale: true,
    });
  });
});
