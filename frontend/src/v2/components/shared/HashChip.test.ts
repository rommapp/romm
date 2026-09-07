import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HashChip from "./HashChip.vue";

const { copy, clipboard } = vi.hoisted(() => ({
  copy: vi.fn(),
  clipboard: { isSupported: true },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ isSupported: clipboard.isSupported, copy }),
}));

const SHA1 = "0123456789abcdef0123456789abcdef01234567";
const ABBREVIATED = "012345…234567";

function mountChip(
  props: Partial<{ label: string; value: string | null }> = {},
) {
  return mount(HashChip, { props: { label: "SHA-1", value: SHA1, ...props } });
}

async function click(wrapper: ReturnType<typeof mountChip>) {
  await wrapper.find("button").trigger("click");
  await flushPromises();
}

beforeEach(() => {
  copy.mockReset();
  copy.mockResolvedValue(true);
  clipboard.isSupported = true;
  document.body.innerHTML = "";
});

describe("HashChip", () => {
  it("abbreviates a long value", () => {
    const wrapper = mountChip();

    expect(wrapper.text()).toContain(ABBREVIATED);
    expect(wrapper.text()).not.toContain(SHA1);
  });

  it("leaves a short value intact", () => {
    const wrapper = mountChip({ label: "CRC", value: "aabbccdd" });

    expect(wrapper.text()).toContain("aabbccdd");
  });

  it("keeps the full value in the title so hover still reads it", () => {
    const wrapper = mountChip();

    expect(wrapper.find("button").attributes("title")).toContain(SHA1);
  });

  it("copies the full value, not the abbreviation", async () => {
    const wrapper = mountChip();

    await click(wrapper);

    expect(copy).toHaveBeenCalledWith(SHA1, expect.anything());
  });

  it("stays abbreviated when the copy succeeds", async () => {
    const wrapper = mountChip();

    await click(wrapper);

    expect(wrapper.text()).toContain(ABBREVIATED);
    expect(wrapper.text()).not.toContain(SHA1);
  });

  // The core of #4082: over plain HTTP the clipboard API does not exist,
  // so a copy can never succeed. Revealing the value is the only way the
  // user can get at it.
  it("reveals the full value instead of copying when the clipboard is unavailable", async () => {
    clipboard.isSupported = false;
    const wrapper = mountChip();

    await click(wrapper);

    expect(copy).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain(SHA1);
  });

  it("marks a revealed chip so its value can be selected", async () => {
    clipboard.isSupported = false;
    const wrapper = mountChip();

    await click(wrapper);

    expect(wrapper.find("button").classes()).toContain(
      "r-v2-hash-chip--revealed",
    );
  });

  it("collapses the value again on a second click", async () => {
    clipboard.isSupported = false;
    const wrapper = mountChip();

    await click(wrapper);
    await click(wrapper);

    expect(wrapper.text()).toContain(ABBREVIATED);
    expect(wrapper.text()).not.toContain(SHA1);
  });

  it("still collapses when the page selection is outside the chip", async () => {
    clipboard.isSupported = false;
    const wrapper = mountChip();
    const outside = document.createElement("p");
    outside.textContent = "selected elsewhere";
    document.body.appendChild(outside);

    await click(wrapper);
    window.getSelection()?.selectAllChildren(outside);
    await click(wrapper);

    expect(wrapper.text()).toContain(ABBREVIATED);
    expect(wrapper.text()).not.toContain(SHA1);
  });

  it("reveals the full value when an attempted copy fails", async () => {
    copy.mockResolvedValue(false);
    const wrapper = mountChip();

    await click(wrapper);

    expect(copy).toHaveBeenCalled();
    expect(wrapper.text()).toContain(SHA1);
  });
});
