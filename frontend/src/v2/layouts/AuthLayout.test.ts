import { mount } from "@vue/test-utils";
import mitt from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { Events } from "@/types/emitter";
import AuthLayout from "./AuthLayout.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  installBreakpointAttribute: vi.fn(),
}));

vi.mock("@/v2/composables/useInputModality", () => ({
  useInputModality: () => ({ install: vi.fn() }),
}));

describe("AuthLayout", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("renders snackbar events from auth views", async () => {
    const emitter = mitt<Events>();
    const wrapper = mount(AuthLayout, {
      global: {
        provide: { emitter },
        stubs: {
          LanguageSelector: true,
          RIcon: true,
          RouterView: true,
          VersionTag: true,
        },
      },
    });

    emitter.emit("snackbarShow", {
      msg: "Unable to register user",
      color: "error",
      timeout: 0,
    });
    await nextTick();

    expect(wrapper.text()).toContain("Unable to register user");
  });
});
