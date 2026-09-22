import { createPinia, setActivePinia } from "pinia";
import { beforeAll, describe, expect, it, vi } from "vitest";
import i18n, { localesReady } from "@/locales";
import router, { ROUTES } from "@/plugins/router";
import storeAuth from "@/stores/auth";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { User } from "@/stores/users";

const { getRom } = vi.hoisted(() => ({ getRom: vi.fn() }));

vi.mock("@/services/api/rom", () => ({
  default: { getRom },
}));

function makeRom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 1,
    name: "Chrono Trigger",
    ...overrides,
  } as unknown as DetailedRom;
}

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

describe("the rom route", () => {
  beforeAll(async () => {
    setActivePinia(createPinia());
    await localesReady;
  });

  // A play page writes saves server-side and then navigates here, so an id
  // matching the route is not proof the store's copy is current.
  it("re-reads a rom the store already holds", async () => {
    const roms = storeRoms();
    storeAuth().setCurrentUser({ id: 1 } as User);
    roms.setCurrentRom(makeRom({ id: 9, name: "before the session" }));
    getRom.mockResolvedValue({
      data: makeRom({ id: 9, name: "after the session" }),
    });

    await router.push({ name: ROUTES.ROM, params: { rom: 9 } });

    expect(getRom).toHaveBeenCalledWith({ romId: 9 });
    expect(roms.currentRom?.name).toBe("after the session");
  });
});
