import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { matchPreferredLocale } from "@/locales";
import storeLanguage from "@/stores/language";

describe("matchPreferredLocale", () => {
  const available = ["en_US", "en_GB", "fr_FR", "zh_CN", "zh_TW"];

  it("prefers an exact region match", () => {
    expect(matchPreferredLocale(["en-GB"], available)).toBe("en_GB");
    expect(matchPreferredLocale(["zh-TW"], available)).toBe("zh_TW");
  });

  it("falls back to a language-only match", () => {
    expect(matchPreferredLocale(["fr-CA"], available)).toBe("fr_FR");
    expect(matchPreferredLocale(["fr"], available)).toBe("fr_FR");
  });

  it("walks the preferences in order", () => {
    expect(matchPreferredLocale(["nl-NL", "fr-BE", "en-US"], available)).toBe(
      "fr_FR",
    );
  });

  it("returns undefined when nothing matches", () => {
    expect(matchPreferredLocale(["nl-NL"], available)).toBeUndefined();
    expect(matchPreferredLocale([], available)).toBeUndefined();
  });
});

describe("language store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("detects the language from the given preferences", () => {
    const store = storeLanguage();
    expect(store.detectBrowserLanguage(["de-AT", "en-US"]).value).toBe("de_DE");
  });

  it("falls back to the default language", () => {
    const store = storeLanguage();
    expect(store.detectBrowserLanguage(["nl-NL"])).toEqual(
      store.defaultLanguage,
    );
  });
});
