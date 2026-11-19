/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import mameApi from "@/services/api/mame";
import taskApi from "@/services/api/task";
import { platformFixture } from "@/utils/platform.fixtures";
import MameMatchDialog from "./MameMatchDialog.vue";

vi.mock("vue-i18n");

vi.mock("@/services/api/mame", () => ({
  default: { getIndexStatus: vi.fn(), matchPlatform: vi.fn() },
}));

vi.mock("@/services/api/task", () => ({
  default: { getTaskById: vi.fn() },
}));

vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/components/shared/PlatformIcon.vue", () => ({
  default: defineComponent({ template: "<i />" }),
}));

vi.mock("@/lib", () => ({
  RDialog: defineComponent({
    props: { modelValue: { type: Boolean, default: false } },
    template:
      "<div v-if='modelValue'><slot name='content' /><slot name='footer' /></div>",
  }),
  RBtn: defineComponent({
    props: { disabled: { type: Boolean, default: false } },
    emits: ["click"],
    template:
      "<button class='start' :disabled='disabled' @click=\"$emit('click')\"><slot /></button>",
  }),
  RAlert: defineComponent({ template: "<p class='alert'><slot /></p>" }),
  RProgressLinear: defineComponent({ template: "<progress />" }),
  RSegmentedControl: defineComponent({
    props: { modelValue: { type: String, default: null } },
    template: "<div class='source'>{{ modelValue }}</div>",
  }),
  RSwitch: defineComponent({ template: "<input type='checkbox' />" }),
}));

vi.mock("@/stores/galleryRoms", () => ({
  default: () => ({
    invalidateWindows: vi.fn(),
    fetchInitialMetadata: vi.fn(),
  }),
}));

function mountDialog() {
  return mount(MameMatchDialog, {
    props: {
      modelValue: true,
      platform: platformFixture({ id: 7, slug: "arcade", rom_count: 3 }),
    },
  });
}

describe("MameMatchDialog", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.mocked(mameApi.getIndexStatus).mockResolvedValue({
      loaded: false,
      info: null,
      updating: false,
    });
  });

  it("says when no listxml is loaded", async () => {
    const wrapper = mountDialog();
    await flushPromises();

    expect(wrapper.find(".source").text()).toBe("match");
    expect(wrapper.find(".alert").text()).toBe("platform.mame-match-no-index");
  });

  it("queues the match and follows the task", async () => {
    vi.useFakeTimers();
    vi.mocked(mameApi.matchPlatform).mockResolvedValue({
      task_id: "job-1",
    } as Awaited<ReturnType<typeof mameApi.matchPlatform>>);
    vi.mocked(taskApi.getTaskById).mockResolvedValue({
      data: { status: "started", meta: { update_stats: { processed: 1, total: 3 } } },
    } as Awaited<ReturnType<typeof taskApi.getTaskById>>);

    const wrapper = mountDialog();
    await flushPromises();
    await wrapper.find("button.start").trigger("click");
    await flushPromises();

    expect(mameApi.matchPlatform).toHaveBeenCalledWith({
      platform_id: 7,
      action: "match",
      rename: true,
    });

    await vi.advanceTimersByTimeAsync(1500);
    await flushPromises();
    expect(taskApi.getTaskById).toHaveBeenCalledWith("job-1");
    expect(wrapper.find("[data-testid=mame-match-progress]").text()).toContain(
      "platform.mame-match-running",
    );
    vi.useRealTimers();
  });
});
