import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { rom } from "@/v2/components/Gallery/listRowFixture";
import ShowQRCodeDialog from "./ShowQRCodeDialog.vue";

// Each encode waits for releaseQR() so a test can look between the link
// changing and the new image arriving.
const { toDataURL, releaseQR } = vi.hoisted(() => {
  let pending: Array<() => void> = [];
  return {
    toDataURL: vi.fn(
      (text: string) =>
        new Promise<string>((resolve) =>
          pending.push(() => resolve(`qr:${text}`)),
        ),
    ),
    releaseQR: () => {
      pending.forEach((resolve) => resolve());
      pending = [];
    },
  };
});

vi.mock("vue-i18n");

vi.mock("qrcode", () => ({ default: { toDataURL } }));

vi.mock("@/utils", () => ({
  isNintendoDSFile: () => true,
  getNintendoDSFiles: () => [],
  getDownloadLink: ({ rom }: { rom: SimpleRom }) => `link-${rom.id}`,
}));

function mountDialog(): { wrapper: VueWrapper; emitter: Emitter<Events> } {
  const emitter = mitt<Events>();
  const wrapper = mount(ShowQRCodeDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          template: '<div v-if="modelValue"><slot name="content" /></div>',
        },
      },
    },
  });
  return { wrapper, emitter };
}

describe("ShowQRCodeDialog", () => {
  it("encodes the ROM's download link", async () => {
    const { wrapper, emitter } = mountDialog();

    emitter.emit("showQRCodeDialog", rom({ id: 1 }));
    await flushPromises();
    releaseQR();
    await flushPromises();

    expect(wrapper.get(".r-v2-qr__code").attributes("src")).toBe("qr:link-1");
  });

  it("never shows the previous ROM's code while the next one encodes", async () => {
    const { wrapper, emitter } = mountDialog();
    emitter.emit("showQRCodeDialog", rom({ id: 1 }));
    await flushPromises();
    releaseQR();
    await flushPromises();

    emitter.emit("showQRCodeDialog", rom({ id: 2 }));
    await flushPromises();
    expect(wrapper.find(".r-v2-qr__code").exists()).toBe(false);

    releaseQR();
    await flushPromises();
    expect(wrapper.get(".r-v2-qr__code").attributes("src")).toBe("qr:link-2");
  });
});
