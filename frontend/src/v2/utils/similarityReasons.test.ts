import { describe, expect, it } from "vitest";
import type { SimilarityReasonSchema } from "@/__generated__";
import { reasonIcon, reasonLabel } from "@/v2/utils/similarityReasons";

function reason(facet: string, value = "x"): SimilarityReasonSchema {
  return { facet, value } as SimilarityReasonSchema;
}

const DEFAULT_ICON = "mdi-tag-outline";

describe("reasonIcon", () => {
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
  ])("maps %s to a dedicated icon", (facet) => {
    expect(reasonIcon(reason(facet))).not.toBe(DEFAULT_ICON);
  });

  it("falls back for a facet it does not know", () => {
    expect(reasonIcon(reason("something_new"))).toBe(DEFAULT_ICON);
  });
});

describe("reasonLabel", () => {
  const t = (key: string) => key;

  it("shows the value for facets that are already proper nouns", () => {
    expect(reasonLabel(reason("developer", "Treasure"), t)).toBe("Treasure");
  });

  it("pluralises a decade", () => {
    expect(reasonLabel(reason("decade", "1990"), t)).toBe("1990s");
  });

  it("translates facets with no meaningful value", () => {
    expect(reasonLabel(reason("igdb", ""), t)).toBe(
      "recommendations.reason-igdb",
    );
  });
});
