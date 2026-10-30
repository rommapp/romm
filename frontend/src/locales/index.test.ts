import { afterEach, describe, expect, it } from "vitest";
import i18n, { czechPluralIndex, loadLocale } from "@/locales";

describe("czechPluralIndex", () => {
  it("maps counts onto four forms", () => {
    expect([0, 1, 2, 4, 5, 22].map((n) => czechPluralIndex(n, 4))).toEqual([
      0, 1, 2, 2, 3, 3,
    ]);
  });

  it("maps counts onto one/other forms", () => {
    expect([0, 1, 2, 5].map((n) => czechPluralIndex(n, 2))).toEqual([
      1, 0, 1, 1,
    ]);
  });
});

describe("cs_CZ messages", () => {
  afterEach(() => {
    i18n.global.locale.value = "en_US";
  });

  it("renders both plural shapes", async () => {
    await loadLocale("cs_CZ");
    i18n.global.locale.value = "cs_CZ";
    const { t } = i18n.global;

    expect([1, 2].map((n) => t("common.platforms-n", { n }))).toEqual([
      "1 platforma",
      "2 platformy",
    ]);
    expect(() => t("common.platforms-n", { n: 5 })).not.toThrow();
    expect(
      [1, 3, 5].map((count) => t("common.upload-files-selected", { count })),
    ).toEqual([
      "1 soubor k nahrání",
      "3 soubory k nahrání",
      "5 souborů k nahrání",
    ]);
  });
});
