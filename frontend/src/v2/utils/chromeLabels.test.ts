import { mount } from "@vue/test-utils";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import i18n, { loadLocale } from "@/locales";
import {
  ChromeLabelsKey,
  DEFAULT_CHROME_LABELS,
  useChromeLabels,
} from "@/v2/lib/a11y/chromeLabels";
import { createChromeLabels } from "./chromeLabels";

// Catches a label pointing at a key no locale defines, and the provider
// coming unwired. A key missing from one locale falls back to en_US rather
// than to the key, so that case stays the parity checker's job.
const STRING_KEYS = (
  Object.keys(DEFAULT_CHROME_LABELS) as (keyof typeof DEFAULT_CHROME_LABELS)[]
).filter((key) => typeof DEFAULT_CHROME_LABELS[key] === "string");

const LOCALES_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../locales",
);

const locales = readdirSync(LOCALES_DIR, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && entry.name !== "__pycache__")
  .map((entry) => entry.name);

beforeAll(async () => {
  await Promise.all(locales.map((locale) => loadLocale(locale)));
});

afterEach(() => {
  i18n.global.locale.value = "en_US";
});

describe("createChromeLabels", () => {
  it("covers every string label in the contract", () => {
    expect(STRING_KEYS.length).toBe(
      Object.keys(DEFAULT_CHROME_LABELS).length - 1,
    );
  });

  describe.each(locales)("%s", (locale) => {
    it.each(STRING_KEYS)("resolves %s", (key) => {
      i18n.global.locale.value = locale;
      const value = createChromeLabels()[key] as string;
      expect(value, key).toBeTruthy();
      // An unresolved key comes back as the key itself.
      expect(value, key).not.toMatch(/^common\./);
      expect(value.trim(), key).toBe(value);
    });

    it("interpolates the stepper label", () => {
      i18n.global.locale.value = locale;
      const value = createChromeLabels().step(2, 5);
      expect(value).not.toMatch(/^common\./);
      expect(value).toContain("2");
      expect(value).toContain("5");
      expect(value).not.toContain("{");
    });
  });

  it("differs from English in a translated locale", () => {
    i18n.global.locale.value = "de_DE";
    const german = createChromeLabels().close;
    i18n.global.locale.value = "en_US";
    expect(german).not.toBe(createChromeLabels().close);
  });
});

// The point of getters over a snapshot: an already-mounted primitive picks
// up a locale switch on its own, with no forced re-render.
describe("a live locale switch reaches a mounted component", () => {
  const Consumer = {
    setup() {
      return { labels: useChromeLabels() };
    },
    template: `<i>{{ labels.close }}</i>`,
  };

  it("re-renders the label when i18n.global.locale changes", async () => {
    i18n.global.locale.value = "en_US";
    const wrapper = mount(Consumer, {
      global: {
        provide: { [ChromeLabelsKey as symbol]: createChromeLabels() },
      },
    });
    expect(wrapper.text()).toBe("Close");

    i18n.global.locale.value = "de_DE";
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toBe("Schließen");
    wrapper.unmount();
  });
});
