import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";

// `enteredFromGallery` is a module-level singleton, so each case re-imports
// the module to start from a known-false flag.
async function loadFresh() {
  vi.resetModules();
  return import("./index");
}

const blank = { template: "<div />" };

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: ROUTES.HOME, component: blank },
      { path: "/platform/:platform", name: ROUTES.PLATFORM, component: blank },
      { path: "/rom/:rom", name: ROUTES.ROM, component: blank },
      { path: "/play/:rom", name: ROUTES.EMULATORJS, component: blank },
    ],
  });
}

describe("useGalleryProvenance", () => {
  it("arms on a gallery → details click-through", async () => {
    const mod = await loadFresh();
    const router = makeRouter();
    mod.installGalleryProvenance(router);

    await router.push("/platform/1");
    await router.push("/rom/10");

    expect(mod.useGalleryProvenance().enteredFromGallery.value).toBe(true);
  });

  it("stays disarmed when the details view is opened from outside a gallery", async () => {
    const mod = await loadFresh();
    const router = makeRouter();
    mod.installGalleryProvenance(router);

    await router.push("/");
    await router.push("/rom/10");

    expect(mod.useGalleryProvenance().enteredFromGallery.value).toBe(false);
  });

  it("disarms once a ROM is opened from outside the gallery it came from", async () => {
    const mod = await loadFresh();
    const router = makeRouter();
    mod.installGalleryProvenance(router);

    await router.push("/platform/1");
    await router.push("/rom/10");
    await router.push("/");
    await router.push("/rom/11");

    expect(mod.useGalleryProvenance().enteredFromGallery.value).toBe(false);
  });

  it("keeps the arming across rom → rom hops and a play session", async () => {
    const mod = await loadFresh();
    const router = makeRouter();
    mod.installGalleryProvenance(router);

    await router.push("/platform/1");
    await router.push("/rom/10");
    await router.push("/rom/11");
    await router.push("/play/11");
    await router.push("/rom/11");

    expect(mod.useGalleryProvenance().enteredFromGallery.value).toBe(true);
  });

  it("stops tracking once the guard is removed", async () => {
    const mod = await loadFresh();
    const router = makeRouter();
    const remove = mod.installGalleryProvenance(router);

    await router.push("/platform/1");
    remove();
    await router.push("/rom/10");

    expect(mod.useGalleryProvenance().enteredFromGallery.value).toBe(false);
  });
});
