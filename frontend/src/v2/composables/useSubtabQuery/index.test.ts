import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { defineComponent, type Ref, ref } from "vue";
import {
  createMemoryHistory,
  createRouter,
  type LocationQueryRaw,
} from "vue-router";
import { installQueryNavigationGuard } from "@/v2/utils/routeQuery";
import { useSubtabQuery } from "./index";

type Subtab = "saves" | "states";
const SUBTABS: readonly string[] = ["saves", "states"];

async function mountAt(
  query: LocationQueryRaw,
  valid: Ref<readonly string[]> = ref(SUBTABS),
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/rom/:id", component: { template: "<div />" } }],
  });
  await router.push({ path: "/rom/1", query });

  let subtab!: Ref<Subtab>;
  const Host = defineComponent({
    setup() {
      subtab = useSubtabQuery<Subtab>(
        "save-data",
        (value) => valid.value.includes(value),
        "saves",
      );
      return () => null;
    },
  });
  mount(Host, { global: { plugins: [router] } });
  return { router, subtab };
}

describe("useSubtabQuery", () => {
  it("reads the subtab when the URL is on its tab", async () => {
    const { subtab } = await mountAt({ tab: "save-data", subtab: "states" });

    expect(subtab.value).toBe("states");
  });

  it("ignores a subtab left over from another tab", async () => {
    const { subtab } = await mountAt({ tab: "media", subtab: "states" });

    expect(subtab.value).toBe("saves");
  });

  it("falls back on an unknown subtab", async () => {
    const { subtab } = await mountAt({ tab: "save-data", subtab: "manual" });

    expect(subtab.value).toBe("saves");
  });

  it("writes a change back to the URL", async () => {
    const { router, subtab } = await mountAt({ tab: "save-data" });

    subtab.value = "states";
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({
      tab: "save-data",
      subtab: "states",
    });
  });

  it("follows an external navigation to another subtab", async () => {
    const { router, subtab } = await mountAt({ tab: "save-data" });

    await router.push({
      path: "/rom/1",
      query: { tab: "save-data", subtab: "states" },
    });
    await flushPromises();

    expect(subtab.value).toBe("states");
  });

  it("rewrites an unknown subtab in the URL to the one shown", async () => {
    const { router } = await mountAt({ tab: "save-data", subtab: "manual" });
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({
      tab: "save-data",
      subtab: "saves",
    });
  });

  it("rewrites a subtab carried to a page that can't show it", async () => {
    const valid = ref<readonly string[]>(SUBTABS);
    const { router, subtab } = await mountAt(
      { tab: "save-data", subtab: "states" },
      valid,
    );
    installQueryNavigationGuard(router);
    // Like GameDetails' `onBeforeRouteUpdate`, the next game lands in the
    // store before the route commits, and it has no states.
    router.beforeResolve((to) => {
      if (to.path !== "/rom/2") return;
      valid.value = ["saves"];
      subtab.value = "saves";
    });

    await router.push({
      path: "/rom/2",
      query: { tab: "save-data", subtab: "states" },
    });
    await flushPromises();

    expect(router.currentRoute.value.fullPath).toBe(
      "/rom/2?tab=save-data&subtab=saves",
    );
  });

  it("leaves a subtab that belongs to another tab alone", async () => {
    const { router } = await mountAt({ tab: "media", subtab: "manual" });
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({
      tab: "media",
      subtab: "manual",
    });
  });
});
