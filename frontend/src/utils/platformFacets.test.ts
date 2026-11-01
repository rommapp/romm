import { describe, expect, it } from "vitest";
import {
  facetOptions,
  filterByFacets,
  formatFacetParam,
  parseFacetParam,
} from "@/utils/platformFacets";

type Key = "category" | "play";
interface Item {
  name: string;
  category: string;
  play: string[];
}

const items: Item[] = [
  { name: "snes", category: "console", play: ["browser"] },
  { name: "gba", category: "portable", play: ["browser", "stream"] },
  { name: "ps2", category: "console", play: [] },
  { name: "dos", category: "computer", play: ["browser"] },
];

const valuesOf = (item: Item, key: Key): readonly string[] =>
  key === "category" ? [item.category] : item.play;

const names = (list: Item[]) => list.map((i) => i.name);

describe("filterByFacets", () => {
  it("returns everything when nothing is picked", () => {
    expect(names(filterByFacets(items, { category: [] }, valuesOf))).toEqual([
      "snes",
      "gba",
      "ps2",
      "dos",
    ]);
  });

  it("ORs values within a facet and ANDs across facets", () => {
    const picked = filterByFacets(
      items,
      { category: ["console", "portable"], play: ["browser"] },
      valuesOf,
    );
    expect(names(picked)).toEqual(["snes", "gba"]);
  });

  it("ignores the excepted facet", () => {
    const picked = filterByFacets(
      items,
      { category: ["computer"], play: ["stream"] },
      valuesOf,
      "category",
    );
    expect(names(picked)).toEqual(["gba"]);
  });
});

describe("facetOptions", () => {
  it("counts each option against the other facets only", () => {
    const options = facetOptions(
      items,
      "category",
      { category: ["console"], play: ["browser"] },
      valuesOf,
      (v) => v,
    );
    expect(options).toEqual([
      { value: "computer", label: "computer", count: 1 },
      { value: "console", label: "console", count: 1 },
      { value: "portable", label: "portable", count: 1 },
    ]);
  });

  it("keeps options the other facets narrow to zero", () => {
    const options = facetOptions(
      items,
      "category",
      { play: ["stream"] },
      valuesOf,
      (v) => v,
    );
    expect(options.find((o) => o.value === "console")?.count).toBe(0);
  });

  it("lists a selected value even when no item carries it", () => {
    const options = facetOptions(
      items,
      "category",
      { category: ["arcade"] },
      valuesOf,
      (v) => v.toUpperCase(),
    );
    expect(options[0]).toEqual({ value: "arcade", label: "ARCADE", count: 0 });
  });

  it("honours a custom order", () => {
    const options = facetOptions(
      items,
      "play",
      {},
      valuesOf,
      (v) => v,
      (a, b) => b.count - a.count,
    );
    expect(options.map((o) => o.value)).toEqual(["browser", "stream"]);
  });
});

describe("facet query params", () => {
  it("round-trips, dropping empties and duplicates", () => {
    expect(parseFacetParam("")).toEqual([]);
    expect(parseFacetParam("a,,b,a")).toEqual(["a", "b"]);
    expect(formatFacetParam(["a", "b", "a"])).toBe("a,b");
  });
});
