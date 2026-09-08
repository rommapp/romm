import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import { installOverlayRouteDismiss } from "./index";

const Blank = { template: "<div />" };

function makeRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "home", component: Blank },
      { path: "/rom/:id", name: "rom", component: Blank },
    ],
  });
  const remove = installOverlayRouteDismiss(router);
  return { router, remove };
}

function openOverlay(persistent = false): {
  entry: EscapableEntry;
  close: ReturnType<typeof vi.fn>;
} {
  const close = vi.fn();
  const entry: EscapableEntry = { close, persistent };
  pushEscapable(entry);
  return { entry, close };
}

describe("installOverlayRouteDismiss", () => {
  it("closes open overlays when the route changes", async () => {
    const { router, remove } = makeRouter();
    await router.push("/rom/1");
    const { entry, close } = openOverlay();

    await router.push("/");

    expect(close).toHaveBeenCalledTimes(1);
    popEscapable(entry);
    remove();
  });

  // A persistent dialog only blocks Esc / scrim clicks; once the page it
  // belonged to is gone it has nothing left to guard.
  it("closes persistent overlays too", async () => {
    const { router, remove } = makeRouter();
    await router.push("/rom/1");
    const { entry, close } = openOverlay(true);

    await router.push("/");

    expect(close).toHaveBeenCalledTimes(1);
    popEscapable(entry);
    remove();
  });

  // Filters, view mode and details subtabs live in the query string and
  // rewrite it via router.replace while the drawer that owns them is open.
  it("leaves overlays open on a query-only navigation", async () => {
    const { router, remove } = makeRouter();
    await router.push("/rom/1");
    const { entry, close } = openOverlay();

    await router.replace({ path: "/rom/1", query: { tab: "saves" } });

    expect(close).not.toHaveBeenCalled();
    popEscapable(entry);
    remove();
  });

  it("closes stacked overlays innermost first", async () => {
    const { router, remove } = makeRouter();
    await router.push("/rom/1");
    const order: string[] = [];
    const outer: EscapableEntry = {
      close: () => order.push("outer"),
      persistent: false,
    };
    const inner: EscapableEntry = {
      close: () => order.push("inner"),
      persistent: false,
    };
    pushEscapable(outer);
    pushEscapable(inner);

    await router.push("/");

    expect(order).toEqual(["inner", "outer"]);
    popEscapable(inner);
    popEscapable(outer);
    remove();
  });

  // End to end over the real primitive: a dialog mounted above the router
  // view (as GlobalDialogs does) must leave the DOM when the route changes.
  it("takes a mounted RDialog off the page", async () => {
    const { router, remove } = makeRouter();
    await router.push("/rom/1");
    const open = ref(true);
    const wrapper = mount(
      {
        components: { RDialog },
        setup: () => ({ open }),
        template: `<RDialog v-model="open"><template #content>body</template></RDialog>`,
      },
      { global: { plugins: [router] } },
    );
    await nextTick();
    expect(document.body.querySelector(".r-dialog")).not.toBeNull();

    await router.push("/");
    await nextTick();

    expect(open.value).toBe(false);
    expect(document.body.querySelector(".r-dialog")).toBeNull();
    wrapper.unmount();
    remove();
  });

  it("stops dismissing once removed", async () => {
    const { router, remove } = makeRouter();
    await router.push("/rom/1");
    const { entry, close } = openOverlay();
    remove();

    await router.push("/");

    expect(close).not.toHaveBeenCalled();
    popEscapable(entry);
  });
});
