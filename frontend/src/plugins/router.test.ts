import { createPinia, setActivePinia } from "pinia";
import { beforeAll, describe, expect, it } from "vitest";
import i18n, { localesReady } from "@/locales";
import router from "@/plugins/router";

describe("route titles", () => {
  beforeAll(async () => {
    setActivePinia(createPinia());
    await localesReady;
  });

  it("stores i18n keys that resolve against the locale messages", () => {
    const titles = router
      .getRoutes()
      .map((route) => route.meta.title)
      .filter((title): title is string => typeof title === "string");

    expect(titles.length).toBeGreaterThan(0);

    for (const title of titles) {
      // Route definitions must hold the key, not an eagerly translated
      // string: messages load after the route table is built.
      expect(title).toMatch(/^[a-z0-9-]+\.[a-z0-9-]+$/);
      expect(i18n.global.t(title)).not.toBe(title);
    }
  });
});
