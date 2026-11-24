import { afterEach, describe, expect, it } from "vitest";
import i18n, {
  availableLocales,
  czechPluralIndex,
  loadLocale,
  matchPreferredLocale,
  ukrainianPluralIndex,
} from "@/locales";
import englishSettings from "./en_US/settings.json";
import englishSetup from "./en_US/setup.json";
import ukrainianSettings from "./uk_UA/settings.json";
import ukrainianSetup from "./uk_UA/setup.json";

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

describe("uk_UA messages", () => {
  afterEach(() => {
    i18n.global.locale.value = "en_US";
  });

  it("maps simple and explicit-zero plurals", () => {
    expect([0, 1, 2, 21].map((n) => ukrainianPluralIndex(n, 2))).toEqual([
      1, 0, 1, 1,
    ]);
    expect(
      [0, 1, 2, 5, 11, 14, 21, 22, 1.5].map((n) => ukrainianPluralIndex(n, 4)),
    ).toEqual([0, 1, 2, 3, 3, 3, 1, 2, 3]);
  });

  it("selects the Ukrainian browser locale and renders game counts", async () => {
    expect(matchPreferredLocale(["uk-UA"], availableLocales)).toBe("uk_UA");
    await loadLocale("uk_UA");
    i18n.global.locale.value = "uk_UA";
    const { t } = i18n.global;
    expect(
      [1, 2, 11, 21, 25].map((n) => t("collection.games-count", n)),
    ).toEqual(["1 гра", "2 гри", "11 ігор", "21 гра", "25 ігор"]);
    expect(t("audit.detail-new-games", 0)).toBe("Нових ігор немає");
  });

  it.each([
    ["setup", englishSetup, ukrainianSetup],
    ["settings", englishSettings, ukrainianSettings],
  ])(
    "preserves environment variable names and assignments in %s",
    (namespace, english, ukrainian) => {
      const translated: Record<string, unknown> = ukrainian;
      const configToken = /\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+(?:=true)?\b/g;
      for (const [key, message] of Object.entries(english)) {
        if (typeof message !== "string") continue;
        const tokens = message.match(configToken);
        if (!tokens) continue;
        const value = translated[key];
        expect(
          typeof value === "string" ? value.match(configToken) : undefined,
          `${namespace}.${key}`,
        ).toEqual(tokens);
      }
    },
  );

  it("renders the correct elapsed-time units", async () => {
    await loadLocale("uk_UA");
    i18n.global.locale.value = "uk_UA";
    const { t } = i18n.global;
    expect(t("activity.days-ago", { n: 2 })).toBe("2 дн. тому");
    expect(t("activity.hours-ago", { n: 1 })).toBe("1 год тому");
    expect(t("activity.hours-minutes-ago", { h: 3, m: 5 })).toBe(
      "3 год 5 хв тому",
    );
    expect(t("activity.minutes-ago", { n: 5 })).toBe("5 хв тому");
  });

  it("warns that a blocked core and its saves may not work", async () => {
    await loadLocale("uk_UA");
    i18n.global.locale.value = "uk_UA";
    const warning = i18n.global.t("play.core-blocked", { core: "Test core" });
    expect(warning).toContain("ядро Test core несправне");
    expect(warning).toContain("ввімкнено експериментальні ядра");
    expect(warning).toContain(
      "Збереження й збережені стани можуть не працювати.",
    );
  });
});

describe("firmware tab messages", () => {
  afterEach(() => {
    i18n.global.locale.value = "en_US";
  });

  it.each([
    ["platform.firmware-missing-from-fs", "Missing from filesystem"],
    [
      "platform.firmware-toggle-all-fs",
      "Also delete all files from filesystem",
    ],
    [
      "platform.firmware-verified-tooltip",
      "Passed size, SHA1 and MD5 checksum checks",
    ],
  ])("translates %s instead of its English fallback", async (key, fallback) => {
    await loadLocale("de_DE");
    i18n.global.locale.value = "de_DE";

    expect(i18n.global.t(key, fallback)).not.toBe(fallback);
  });
});
