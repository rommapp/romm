import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";

const push = vi.fn();
const playingStore = { playing: false };

vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
}));
vi.mock("@/stores/playing", () => ({
  default: () => playingStore,
}));
// The real module instantiates a router at import time.
vi.mock("@/plugins/router", () => ({
  ROUTES: {
    SEARCH: "search",
    HOME: "home",
    PLATFORMS_INDEX: "platforms",
    COLLECTIONS_INDEX: "collections",
  },
}));

// `installed` is module state, so each test gets a fresh module and a fresh
// window listener via a throwaway host component.
async function install() {
  vi.resetModules();
  const { useGlobalHotkeys } = await import("./index");
  const Host = defineComponent({
    setup() {
      useGlobalHotkeys().install();
      return () => h("div");
    },
  });
  return mount(Host);
}

function press(key: string, target: EventTarget = document.body) {
  target.dispatchEvent(
    new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
  );
}

beforeEach(() => {
  push.mockClear();
  playingStore.playing = false;
  document.body.innerHTML = "";
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("useGlobalHotkeys", () => {
  it("routes to search on '/'", async () => {
    const host = await install();
    press("/");
    expect(push).toHaveBeenCalledWith({ name: "search" });
    host.unmount();
  });

  it("ignores keys while the playing flag is set", async () => {
    const host = await install();
    playingStore.playing = true;
    press("/");
    press("g");
    press("h");
    expect(push).not.toHaveBeenCalled();
    host.unmount();
  });

  // The DOSBox case: keys land on <body>, not on a form control, because the
  // emulator canvas reads them off window. Only the playing flag tells them
  // apart from a plain "/" pressed in the gallery.
  it("ignores '/' pressed on the body while a game is running", async () => {
    const host = await install();
    playingStore.playing = true;
    const stage = document.createElement("div");
    stage.id = "game";
    document.body.appendChild(stage);

    press("/");
    expect(push).not.toHaveBeenCalled();
    host.unmount();
  });

  it("ignores keys typed into form fields", async () => {
    const host = await install();
    const input = document.createElement("input");
    document.body.appendChild(input);

    press("/", input);
    expect(push).not.toHaveBeenCalled();
    host.unmount();
  });

  it("still routes 'g h' outside a session", async () => {
    const host = await install();
    press("g");
    press("h");
    expect(push).toHaveBeenCalledWith({ name: "home" });
    host.unmount();
  });
});
