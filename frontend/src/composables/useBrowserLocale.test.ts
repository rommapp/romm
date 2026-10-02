import { useLocalStorage } from "@vueuse/core";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, watch } from "vue";
import type { EffectScope } from "vue";
import { useBrowserLocale } from "@/composables/useBrowserLocale";
import i18n from "@/locales";

const locale = i18n.global.locale;
let browserLanguages: string[] = [];
let scope: EffectScope;

function setBrowserLanguages(languages: string[]) {
  browserLanguages = languages;
  window.dispatchEvent(new Event("languagechange"));
}

function start() {
  scope = effectScope();
  scope.run(() => useBrowserLocale());
}

beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.clear();
  locale.value = "en_US";
  browserLanguages = ["en-US"];
  vi.spyOn(navigator, "languages", "get").mockImplementation(
    () => browserLanguages,
  );
});

afterEach(() => {
  scope.stop();
});

describe("useBrowserLocale", () => {
  it("applies the browser's language when none is stored", async () => {
    browserLanguages = ["fr-CA", "en-US"];
    start();
    await vi.waitFor(() => expect(locale.value).toBe("fr_FR"));
  });

  it("follows browser language changes live", async () => {
    start();
    await nextTick();
    setBrowserLanguages(["de-DE"]);
    await vi.waitFor(() => expect(locale.value).toBe("de_DE"));
  });

  it("keeps a manually picked language over the browser's", async () => {
    localStorage.setItem("settings.locale", "ja_JP");
    browserLanguages = ["fr-FR"];
    start();
    await vi.waitFor(() => expect(locale.value).toBe("ja_JP"));

    setBrowserLanguages(["de-DE"]);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(locale.value).toBe("ja_JP");
  });

  it("picks up a language stored from another component", async () => {
    browserLanguages = ["fr-FR"];
    start();
    await vi.waitFor(() => expect(locale.value).toBe("fr_FR"));

    const picked = useLocalStorage("settings.locale", "");
    picked.value = "it_IT";
    await vi.waitFor(() => expect(locale.value).toBe("it_IT"));

    setBrowserLanguages(["de-DE"]);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(locale.value).toBe("it_IT");
  });

  it("switches only once the language's messages are loaded", async () => {
    const loadedOnSwitch: boolean[] = [];
    const stop = watch(locale, (next) => {
      loadedOnSwitch.push(
        Object.keys(i18n.global.getLocaleMessage(next)).length > 0,
      );
    });
    browserLanguages = ["pl-PL"];
    start();
    await vi.waitFor(() => expect(locale.value).toBe("pl_PL"));
    stop();
    expect(loadedOnSwitch).toEqual([true]);
  });
});
