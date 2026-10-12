import { afterEach, describe, expect, it } from "vitest";
import i18n, { loadLocale } from "@/locales";

const locale = i18n.global.locale;

async function translatePlatformConfirmation(language: string, count: number) {
  await loadLocale(language);
  locale.value = language;
  return i18n.global.t("setup.confirm-create-platforms", count, {
    named: {
      pattern: "/roms/{platform}",
      count,
      plural: count > 1 ? "s" : "",
    },
  });
}

afterEach(() => {
  locale.value = "en_US";
});

describe("setup confirmations", () => {
  it("preserves English suffix interpolation", async () => {
    await expect(translatePlatformConfirmation("en_US", 2)).resolves.toContain(
      "2 platforms.",
    );
  });

  it("uses Swedish singular and plural platform forms", async () => {
    await expect(translatePlatformConfirmation("sv_SE", 1)).resolves.toContain(
      "1 plattform.",
    );
    await expect(translatePlatformConfirmation("sv_SE", 2)).resolves.toContain(
      "2 plattformar.",
    );
  });
});
