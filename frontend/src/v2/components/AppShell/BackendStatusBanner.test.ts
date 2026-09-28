import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import storePlaying from "@/stores/playing";
import BackendStatusBanner from "./BackendStatusBanner.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const isOffline = ref(false);
const isWebSocketDegraded = ref(false);
const retryNow = vi.fn();
const retryWebSocket = vi.fn();

vi.mock("@/v2/composables/useServerConnection", () => ({
  useServerConnection: () => ({ isOffline, retryNow }),
}));

vi.mock("@/v2/composables/useSocketTransportHealth", () => ({
  useSocketTransportHealth: () => ({ isWebSocketDegraded, retryWebSocket }),
}));

vi.mock("@v2/lib", () => ({
  RBtn: { name: "RBtn", template: "<button><slot /></button>" },
  RIcon: { name: "RIcon", template: "<i />" },
  RTooltip: {
    name: "RTooltip",
    props: ["text", "activator", "location"],
    template: "<span class='r-tooltip-stub' />",
  },
}));

let wrapper: ReturnType<typeof mount> | null = null;

async function render() {
  wrapper = mount(BackendStatusBanner);
  await wrapper.vm.$nextTick();
}

const banner = () => wrapper!.find(".r-backend-banner");
const body = () => wrapper!.find(".r-backend-banner__body");

describe("BackendStatusBanner", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    isOffline.value = false;
    isWebSocketDegraded.value = false;
    retryNow.mockClear();
    retryWebSocket.mockClear();
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    vi.useRealTimers();
  });

  it("stays out of sight while the server answers", async () => {
    await render();

    expect(banner().exists()).toBe(false);
  });

  it("shows the websocket message when HTTP is up but transport is degraded", async () => {
    isWebSocketDegraded.value = true;

    await render();

    expect(banner().exists()).toBe(true);
    expect(wrapper!.text()).toContain("common.websocket-unreachable-retrying");
  });

  it("prefers the offline message when both HTTP and websocket are down", async () => {
    isOffline.value = true;
    isWebSocketDegraded.value = true;

    await render();

    expect(wrapper!.text()).toContain("common.server-offline-retrying");
    expect(wrapper!.text()).not.toContain(
      "common.websocket-unreachable-retrying",
    );
  });

  it("retries the websocket when the degraded banner retry is clicked", async () => {
    isWebSocketDegraded.value = true;

    await render();
    await wrapper!.find(".r-backend-banner__retry").trigger("click");

    expect(retryWebSocket).toHaveBeenCalledOnce();
    expect(retryNow).not.toHaveBeenCalled();
  });

  it("offers the retry button outside a game", async () => {
    isOffline.value = true;

    await render();

    expect(banner().classes()).not.toContain("r-backend-banner--in-game");
    expect(wrapper!.find(".r-backend-banner__retry").exists()).toBe(true);
    // The message is right there to read, so nothing hovers over it.
    expect(wrapper!.find(".r-tooltip-stub").exists()).toBe(false);
  });

  // A notice the player cannot dismiss has no business sitting over the game.
  it("shrinks to its icon once a game has been running a while", async () => {
    isOffline.value = true;
    storePlaying().setPlaying(true);

    await render();
    expect(banner().classes()).toContain("r-backend-banner--in-game");
    expect(body().exists()).toBe(true);
    expect(wrapper!.find(".r-backend-banner__retry").exists()).toBe(false);

    await vi.advanceTimersByTimeAsync(6000);
    await wrapper!.vm.$nextTick();

    expect(body().exists()).toBe(false);
    expect(banner().classes()).toContain("r-backend-banner--collapsed");
    // Only the icon is left, so the message moves into a tooltip of our own.
    expect(wrapper!.find(".r-tooltip-stub").exists()).toBe(true);
  });

  it("says its piece again in full once the game is over", async () => {
    isOffline.value = true;
    const playing = storePlaying();
    playing.setPlaying(true);

    await render();
    await vi.advanceTimersByTimeAsync(6000);
    await wrapper!.vm.$nextTick();
    expect(body().exists()).toBe(false);

    playing.setPlaying(false);
    await wrapper!.vm.$nextTick();

    expect(body().exists()).toBe(true);
    expect(wrapper!.find(".r-backend-banner__retry").exists()).toBe(true);
  });
});
