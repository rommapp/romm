import { describe, expect, it } from "vitest";
import type { Facet, SimilarityReasonSchema } from "@/__generated__";
import { reasonIcon, reasonLabel } from "@/v2/utils/similarityReasons";

function reason(facet: Facet, value = "x"): SimilarityReasonSchema {
  return { facet, value };
}

describe("reasonIcon", () => {
  // There is no fallback to test: FACET_ICONS is keyed by the generated
  // `Facet` union, so an unmapped facet fails the typecheck rather than
  // silently rendering a generic tag.
  it.each([
    "collection",
    "franchise",
    "developer",
    "publisher",
    "company",
    "genre",
    "theme",
    "perspective",
    "keyword",
    "game_mode",
    "platform",
    "decade",
    "igdb",
    "top_rated",
  ] satisfies Facet[])("maps %s to an icon", (facet) => {
    expect(reasonIcon(reason(facet))).toMatch(/^mdi-/);
  });
});

describe("reasonLabel", () => {
  // Stands in for vue-i18n, rendering the key plus anything interpolated
  // into it. Facets with no value of their own render as the bare key.
  const t = (key: string, params?: unknown[]) =>
    [key, ...(params ?? [])].filter(Boolean).join(":");

  it("shows the value for facets that are already proper nouns", () => {
    expect(reasonLabel(reason("developer", "Treasure"), t)).toBe("Treasure");
  });

  it("hands a decade's year to the locale's phrasing", () => {
    expect(reasonLabel(reason("decade", "1990"), t)).toBe(
      "recommendations.reason-decade:1990",
    );
  });

  it("translates facets with no meaningful value", () => {
    expect(reasonLabel(reason("igdb", ""), t)).toBe(
      "recommendations.reason-igdb",
    );
  });
});
