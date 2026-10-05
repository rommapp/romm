import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { type ComputedRef, defineComponent } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import { romIdFromRoute, useRouteRom } from "./index";

function detailed(id: number) {
  return detailedRomFixture({ id, name: `Game ${id}` });
}

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { render: () => null } },
      { path: "/rom/:rom", component: { render: () => null } },
    ],
  });
  await router.push(path);
  let rom!: ComputedRef<DetailedRom | null>;
  mount(
    defineComponent({
      setup() {
        rom = useRouteRom();
        return () => null;
      },
    }),
    { global: { plugins: [router] } },
  );
  return { router, rom };
}

describe("romIdFromRoute", () => {
  it("reads a numeric :rom param", () => {
    expect(romIdFromRoute({ params: { rom: "12" } })).toBe(12);
  });

  it("is null without a usable :rom param", () => {
    expect(romIdFromRoute({ params: {} })).toBeNull();
    expect(romIdFromRoute({ params: { rom: "abc" } })).toBeNull();
  });
});

describe("useRouteRom", () => {
  it("is the cached record for the route's rom", async () => {
    storeRoms().cacheDetailedRom(detailed(1));
    const { rom } = await mountAt("/rom/1");

    expect(rom.value?.name).toBe("Game 1");
  });

  it("stays on its game while a navigation prefetches the next one", async () => {
    const roms = storeRoms();
    roms.cacheDetailedRom(detailed(1));
    const { router, rom } = await mountAt("/rom/1");
    let seenMidNavigation: number | undefined;
    router.beforeResolve(() => {
      roms.cacheDetailedRom(detailed(2));
      seenMidNavigation = rom.value?.id;
    });

    await router.push("/rom/2");

    expect(seenMidNavigation).toBe(1);
    expect(rom.value?.id).toBe(2);
  });

  it("is null off a rom route", async () => {
    storeRoms().cacheDetailedRom(detailed(1));
    const { rom } = await mountAt("/");

    expect(rom.value).toBeNull();
  });
});
