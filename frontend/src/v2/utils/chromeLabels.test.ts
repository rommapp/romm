import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { beforeAll, describe, expect, it } from "vitest";
import i18n, { loadLocale } from "@/locales";
import { DEFAULT_CHROME_LABELS } from "@/v2/lib/a11y/chromeLabels";
import { createChromeLabels } from "./chromeLabels";

// Catches a label pointing at a key no locale defines, and the provider
// coming unwired. A key missing from one locale falls back to en_US rather
// than to the key, so that case stays the parity checker's job.
const LABEL_KEYS = Object.keys(
  DEFAULT_CHROME_LABELS,
) as (keyof typeof DEFAULT_CHROME_LABELS)[];

const LOCALES_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../locales",
);

const locales = readdirSync(LOCALES_DIR, {
  withFileTypes: true,
})
  .filter((entry) => entry.isDirectory() && entry.name !== "__pycache__")
  .map((entry) => entry.name);

beforeAll(async () => {
  await Promise.all(locales.map((locale) => loadLocale(locale)));
});

describe("createChromeLabels", () => {
  it("covers every label in the contract", () => {
    expect(LABEL_KEYS.length).toBe(Object.keys(DEFAULT_CHROME_LABELS).length);
    expect(LABEL_KEYS.length).toBeGreaterThan(0);
  });

  describe.each(locales)("%s", (locale) => {
    it.each(LABEL_KEYS)("resolves %s", (key) => {
      i18n.global.locale.value = locale;
      const value = createChromeLabels()[key];
      expect(value, key).toBeTruthy();
      // An unresolved key comes back as the key itself.
      expect(value, key).not.toMatch(/^common\./);
      expect(value.trim(), key).toBe(value);
    });
  });

  it("actually differs from English in a translated locale", () => {
    i18n.global.locale.value = "de_DE";
    const german = createChromeLabels().close;
    i18n.global.locale.value = "en_US";
    const english = createChromeLabels().close;
    expect(german).not.toBe(english);
  });
});
