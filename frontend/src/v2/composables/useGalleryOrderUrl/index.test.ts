import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick } from "vue";
import {
  createMemoryHistory,
  createRouter,
  type Router,
  RouterView,
} from "vue-router";
import storeGalleryRoms, {
  DEFAULT_ORDER_BY,
  type GalleryOrderKey,
} from "@/v2/stores/galleryRoms";
import { useGalleryOrderUrl } from "./index";

const Blank = { template: "<div />" };

async function mountAt(
  router: Router,
  path: string,
  defaultOrderBy: GalleryOrderKey | null = DEFAULT_ORDER_BY,
) {
  await router.push(path);
  await router.isReady();
  const Host = {
    setup() {
      useGalleryOrderUrl(defaultOrderBy);
    },
    template: "<div />",
  };
  const wrapper = mount(Host, { global: { plugins: [router] } });
  await nextTick();
  return wrapper;
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/platform/:platform", name: "platform", component: Blank },
      { path: "/search", name: "search", component: Blank },
    ],
  });
}

/** `patchQuery` batches its writes into a `nextTick` callback, and the
 *  `router.replace` it then issues resolves asynchronously. */
async function flushQueryWrite() {
  await nextTick();
  await flushPromises();
}

describe("useGalleryOrderUrl", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("hydrates the store from the URL before the first fetch", async () => {
    const router = makeRouter();
    await mountAt(router, "/platform/1?orderBy=fs_size_bytes&orderDir=desc");

    const gallery = storeGalleryRoms();
    expect(gallery.orderBy).toBe("fs_size_bytes");
    expect(gallery.orderDir).toBe("desc");
  });

  it("falls back to the default sort for missing or unknown params", async () => {
    const gallery = storeGalleryRoms();
    gallery.setOrderBy("created_at");
    gallery.setOrderDir("desc");

    const router = makeRouter();
    await mountAt(router, "/platform/1?orderBy=not_a_column");

    expect(gallery.orderBy).toBe("name");
    expect(gallery.orderDir).toBe("asc");
  });

  it("writes a column-header sort into the query", async () => {
    const router = makeRouter();
    await mountAt(router, "/platform/1");
    const gallery = storeGalleryRoms();

    gallery.setOrderBy("average_rating");
    gallery.setOrderDir("desc");
    await flushQueryWrite();

    expect(router.currentRoute.value.query).toMatchObject({
      orderBy: "average_rating",
      orderDir: "desc",
    });
  });

  // Grid mode exposes only the direction toggle, so a direction-only
  // write has to reach the URL on its own.
  it("writes a direction-only change into the query", async () => {
    const router = makeRouter();
    await mountAt(router, "/platform/1");
    const gallery = storeGalleryRoms();

    gallery.setOrderDir("desc");
    await flushQueryWrite();

    expect(router.currentRoute.value.query.orderDir).toBe("desc");
    expect(router.currentRoute.value.query.orderBy).toBeUndefined();
  });

  it("drops the params when the sort returns to the default", async () => {
    const router = makeRouter();
    await mountAt(router, "/platform/1?orderBy=created_at&orderDir=desc");
    const gallery = storeGalleryRoms();

    gallery.setOrderBy("name");
    gallery.setOrderDir("asc");
    await flushQueryWrite();

    expect(router.currentRoute.value.query.orderBy).toBeUndefined();
    expect(router.currentRoute.value.query.orderDir).toBeUndefined();
  });

  it("follows the URL back to the previous sort on back-navigation", async () => {
    const router = makeRouter();
    await mountAt(router, "/platform/1?orderBy=created_at&orderDir=desc");
    const gallery = storeGalleryRoms();

    await router.push("/platform/1?orderBy=hltb_main_story&orderDir=asc");
    await flushPromises();
    expect(gallery.orderBy).toBe("hltb_main_story");

    router.back();
    await flushPromises();
    expect(gallery.orderBy).toBe("created_at");
    expect(gallery.orderDir).toBe("desc");
  });

  it("leaves unrelated query params alone", async () => {
    const router = makeRouter();
    await mountAt(router, "/platform/1?search=zelda&layout=list");
    const gallery = storeGalleryRoms();

    gallery.setOrderDir("desc");
    await flushQueryWrite();

    expect(router.currentRoute.value.query).toMatchObject({
      search: "zelda",
      layout: "list",
      orderDir: "desc",
    });
  });
});

describe("useGalleryOrderUrl with a relevance default", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  const mountSearch = (router: Router, path: string) =>
    mountAt(router, path, null);

  it("leaves the sort unset when the URL names none", async () => {
    const gallery = storeGalleryRoms();
    gallery.setOrderBy("created_at");

    const router = makeRouter();
    await mountSearch(router, "/search?search=final+fantasy+7");

    expect(gallery.orderBy).toBeNull();
  });

  it("keeps a picked title sort in the query", async () => {
    const router = makeRouter();
    await mountSearch(router, "/search?search=zelda");
    const gallery = storeGalleryRoms();

    gallery.setOrderBy("name");
    await flushQueryWrite();

    expect(router.currentRoute.value.query.orderBy).toBe("name");
  });

  it("drops the param when the sort returns to relevance", async () => {
    const router = makeRouter();
    await mountSearch(router, "/search?search=zelda&orderBy=name");
    const gallery = storeGalleryRoms();
    expect(gallery.orderBy).toBe("name");

    gallery.setOrderBy(null);
    await flushQueryWrite();

    expect(router.currentRoute.value.query.orderBy).toBeUndefined();
  });
});

// `main.ts` mounts without awaiting `router.isReady()`, so setup-only
// hydration holds solely because RouterView withholds the matched component
// until the initial navigation resolves.
describe("useGalleryOrderUrl on a cold load", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("sees the URL in setup() without awaiting router.isReady", async () => {
    const seenAtSetup: (string | null)[] = [];
    const GalleryView = {
      setup() {
        useGalleryOrderUrl(DEFAULT_ORDER_BY);
        seenAtSetup.push(storeGalleryRoms().orderBy);
        return () => h("div");
      },
    };

    const history = createMemoryHistory();
    history.replace("/platform/1?orderBy=average_rating&orderDir=desc");
    const router = createRouter({
      history,
      routes: [{ path: "/platform/:platform", component: GalleryView }],
    });

    const app = createApp({ render: () => h(RouterView) });
    app.use(router);
    app.mount(document.createElement("div"));
    await flushPromises();

    expect(seenAtSetup).toEqual(["average_rating"]);
    expect(storeGalleryRoms().orderDir).toBe("desc");
    app.unmount();
  });
});
