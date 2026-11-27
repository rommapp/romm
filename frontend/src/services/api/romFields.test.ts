import { describe, expect, expectTypeOf, it } from "vitest";
import type { CoverArtRom } from "@/composables/useCoverArt";
import {
  COVER_AND_NAME_FIELDS,
  COVER_ART_FIELDS,
  DEFAULT_ROM_FIELDS,
  difference,
  getFieldsWith,
  getFieldsWithout,
  intersection,
  union,
} from "@/services/api/romFields";

describe("rom field sets", () => {
  it("getFieldsWith keeps exactly the fields it is given", () => {
    expect([...getFieldsWith(["name", "slug"])]).toEqual(["name", "slug"]);
    expect(getFieldsWith().size).toBe(0);
  });

  it("getFieldsWith can ask for files, which the default leaves out", () => {
    expect(DEFAULT_ROM_FIELDS.has("files" as never)).toBe(false);
    expect(getFieldsWith(["files"]).has("files")).toBe(true);
  });

  it("getFieldsWithout drops only the named fields", () => {
    const rest = getFieldsWithout(["igdb_metadata", "ss_metadata"]);

    expect(rest.has("igdb_metadata" as never)).toBe(false);
    expect(rest.has("ss_metadata" as never)).toBe(false);
    expect(rest.size).toBe(DEFAULT_ROM_FIELDS.size - 2);
  });

  it("combines sets", () => {
    const a = getFieldsWith(["name", "slug"]);
    const b = getFieldsWith(["slug", "summary"]);

    expect([...union(a, b)].sort()).toEqual(["name", "slug", "summary"]);
    expect([...intersection(a, b)]).toEqual(["slug"]);
    expect([...difference(a, b)]).toEqual(["name"]);
  });

  it("tracks the names in the type", () => {
    const a = getFieldsWith(["name", "slug"]);
    const b = getFieldsWith(["slug", "summary"]);

    expectTypeOf(union(a, b)).toEqualTypeOf<
      ReadonlySet<"name" | "slug" | "summary">
    >();
    expectTypeOf(intersection(a, b)).toEqualTypeOf<ReadonlySet<"slug">>();
    expectTypeOf(difference(a, b)).toEqualTypeOf<ReadonlySet<"name">>();
  });

  it("covers every field the cover component reads", () => {
    type Listed =
      typeof COVER_ART_FIELDS extends ReadonlySet<infer K> ? K : never;
    expectTypeOf<Exclude<keyof CoverArtRom, Listed>>().toEqualTypeOf<never>();
    expectTypeOf<Exclude<Listed, keyof CoverArtRom>>().toEqualTypeOf<never>();
  });

  it("adds the names to the cover fields for a cover-and-name row", () => {
    expect(COVER_AND_NAME_FIELDS.has("name")).toBe(true);
    expect(COVER_AND_NAME_FIELDS.has("fs_name")).toBe(true);
    for (const field of COVER_ART_FIELDS) {
      expect(COVER_AND_NAME_FIELDS.has(field)).toBe(true);
    }
  });
});
