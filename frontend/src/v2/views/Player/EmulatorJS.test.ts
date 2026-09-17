import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, expect, it, vi } from "vitest";
import EmulatorJS from "./EmulatorJS.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: { emulator?: string }) =>
      params?.emulator ? `${key}:${params.emulator}` : key,
  }),
}));

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: vi.fn(),
  useRoute: () => ({ params: { rom: "1" }, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

// Left pending so the mount stops before the launch screen loads anything.
vi.mock("@/services/api/rom", () => ({
  default: { getRom: () => new Promise(() => {}) },
}));

vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({
    emulatorLabel: (id: string) => (id === "retroarch" ? "RetroArch" : id),
  }),
}));

vi.mock("@/v2/composables/useActivityPresence", () => ({
  useActivityPresence: () => ({ start: vi.fn(), stop: vi.fn() }),
}));

vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));

vi.mock("@/v2/composables/usePageTitle", () => ({ usePageTitle: vi.fn() }));

vi.mock("@/v2/composables/usePlaySession", () => ({
  usePlaySession: () => ({ start: vi.fn(), flush: vi.fn() }),
}));

type EmulatorJSVm = {
  stateDisabledReason: (asset: { emulator?: string | null }) => string | null;
};

describe("EmulatorJS state picker", () => {
  it("names another emulator's state the way the backend labels it", () => {
    const wrapper = mount(EmulatorJS, {
      shallow: true,
      global: { plugins: [createPinia()] },
    });
    const vm = wrapper.vm as unknown as EmulatorJSVm;

    expect(vm.stateDisabledReason({ emulator: "retroarch" })).toBe(
      "play.state-incompatible-core:RetroArch",
    );
    wrapper.unmount();
  });
});
