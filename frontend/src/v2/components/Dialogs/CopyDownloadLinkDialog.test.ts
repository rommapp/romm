import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Events } from "@/types/emitter";
import CopyDownloadLinkDialog from "./CopyDownloadLinkDialog.vue";

const { copy } = vi.hoisted(() => ({ copy: vi.fn() }));

vi.mock("vue-i18n");

vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ isSupported: true, copy }),
}));

const LINK = "http://romm.local/api/roms/1/content/game.zip";

async function open(): Promise<VueWrapper> {
  const emitter = mitt<Events>();
  const wrapper = mount(CopyDownloadLinkDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          template: `<div v-if="modelValue" data-test-dialog>
            <slot name="content" /><slot name="footer" />
          </div>`,
        },
        RBtn: { template: `<button data-test-retry><slot /></button>` },
      },
    },
  });
  emitter.emit("showCopyDownloadLinkDialog", LINK);
  await flushPromises();
  return wrapper;
}

describe("CopyDownloadLinkDialog", () => {
  beforeEach(() => {
    copy.mockReset();
  });

  it("shows the link for a manual copy", async () => {
    const wrapper = await open();

    expect(wrapper.find("code").text()).toBe(LINK);
  });

  it("closes once a retry copies the link", async () => {
    copy.mockResolvedValue(true);
    const wrapper = await open();

    await wrapper.get("[data-test-retry]").trigger("click");
    await flushPromises();

    expect(copy).toHaveBeenCalledWith(
      LINK,
      expect.objectContaining({ errorMessage: "rom.cant-copy-link" }),
    );
    expect(wrapper.find("[data-test-dialog]").exists()).toBe(false);
  });

  it("stays open when the retry fails", async () => {
    copy.mockResolvedValue(false);
    const wrapper = await open();

    await wrapper.get("[data-test-retry]").trigger("click");
    await flushPromises();

    expect(wrapper.find("[data-test-dialog]").exists()).toBe(true);
  });
});
