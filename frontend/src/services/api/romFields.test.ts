import { describe, expect, expectTypeOf, it } from "vitest";
import {
  COVER_AND_NAME_FIELDS,
  COVER_ART_FIELDS,
  GALLERY_FIELDS,
  getFieldsWith,
  union,
  type RomFieldSelection,
} from "@/services/api/romFields";

const omitted: ReadonlySet<string> = GALLERY_FIELDS;

describe("rom field sets", () => {
  it("getFieldsWith keeps exactly the fields it is given", () => {
    expect([...getFieldsWith(["name", "slug"])]).toEqual(["name", "slug"]);
    expect(getFieldsWith().size).toBe(0);
  });

  it("combines sets and tracks the names in the type", () => {
    const both = union(
      getFieldsWith(["name", "slug"]),
      getFieldsWith(["slug", "summary"]),
    );

    expect([...both].sort()).toEqual(["name", "slug", "summary"]);
    expectTypeOf(both).toEqualTypeOf<
      ReadonlySet<"name" | "slug" | "summary">
    >();
  });

  it("adds the names to the cover fields for a cover-and-name row", () => {
    expect(COVER_AND_NAME_FIELDS.has("name")).toBe(true);
    expect(COVER_AND_NAME_FIELDS.has("fs_name")).toBe(true);
    for (const field of COVER_ART_FIELDS) {
      expect(COVER_AND_NAME_FIELDS.has(field)).toBe(true);
    }
  });

  it("states the gallery fields as what to leave out", () => {
    expect(omitted.size).toBeGreaterThan(0);
    for (const field of omitted) expect(field).toMatch(/^-/);
    expect(omitted.has("-igdb_metadata")).toBe(true);
  });

  it("keeps what the edit dialog shows and saves from a gallery rom", () => {
    for (const field of [
      "fs_path",
      "has_multiple_files",
      "manual_metadata",
      "igdb_id",
      "sgdb_id",
      "tgdb_id",
    ]) {
      expect(omitted.has(`-${field}`)).toBe(false);
    }
  });

  it("keeps what a gallery card and row need", () => {
    for (const field of [...COVER_AND_NAME_FIELDS, "hltb_metadata"]) {
      expect(omitted.has(`-${field}`)).toBe(false);
    }
  });

  it("only compiles names the schema has, all kept or all left out", () => {
    const take = (fields: RomFieldSelection): number => fields.size;

    take(new Set(["name"]));
    take(new Set(["-name"]));
    // @ts-expect-error: the schema has no such field
    take(new Set(["nope"]));
    // @ts-expect-error: the schema has no such field to leave out
    take(new Set(["-nope"]));
    // @ts-expect-error: a selection cannot both keep and leave out
    take(new Set(["name", "-slug"]));
  });
});
