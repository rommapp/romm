import { beforeEach, describe, expect, it, vi } from "vitest";
import { reactive } from "vue";
import type { RomUserSchema } from "@/__generated__";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import { usePinnedMedia } from "./index";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api/rom", () => ({
  default: { updateUserRomProps: vi.fn() },
}));

const snackbarError = vi.fn();
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: snackbarError }),
}));

vi.mock("@/v2/utils/pinnedMedia", () => ({
  pinnedMediaKeys: (rom: DetailedRom) =>
    rom.rom_user.pinned_media ?? ["file:1"],
  togglePinnedMediaKey: (keys: string[], key: string) =>
    keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key],
}));

const update = vi.mocked(romApi.updateUserRomProps);

function makeRom(pinnedMedia: string[] | null): DetailedRom {
  return reactive({
    id: 3,
    rom_user: { pinned_media: pinnedMedia } as RomUserSchema,
  }) as DetailedRom;
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve));
}

beforeEach(() => {
  update.mockReset();
  snackbarError.mockReset();
});

describe("usePinnedMedia", () => {
  it("materializes the default selection on the first toggle", async () => {
    update.mockResolvedValue({} as never);
    const rom = makeRom(null);
    const { isPinned, isCustomized, togglePin } = usePinnedMedia(rom);

    expect(isPinned("file:1")).toBe(true);
    expect(isCustomized.value).toBe(false);

    togglePin("file:2");
    expect(rom.rom_user.pinned_media).toEqual(["file:1", "file:2"]);
    expect(isCustomized.value).toBe(true);
    await settle();
    expect(update).toHaveBeenCalledWith({
      romId: 3,
      data: { pinned_media: ["file:1", "file:2"] },
    });
  });

  it("sends rapid toggles one after another, in click order", async () => {
    const releases: (() => void)[] = [];
    update.mockImplementation(
      () => new Promise((resolve) => releases.push(() => resolve({} as never))),
    );
    const { togglePin } = usePinnedMedia(makeRom([]));

    togglePin("file:1");
    togglePin("file:2");
    await settle();
    expect(update).toHaveBeenCalledTimes(1);

    releases[0]();
    await settle();
    expect(update).toHaveBeenCalledTimes(2);
    expect(update.mock.calls[1][0].data).toEqual({
      pinned_media: ["file:1", "file:2"],
    });
  });

  it("restores the previous pins and reports a failed write", async () => {
    update.mockRejectedValue(new Error("offline"));
    const rom = makeRom(["file:1"]);
    const { togglePin } = usePinnedMedia(rom);

    togglePin("file:1");
    expect(rom.rom_user.pinned_media).toEqual([]);
    await settle();
    expect(rom.rom_user.pinned_media).toEqual(["file:1"]);
    expect(snackbarError).toHaveBeenCalledWith(
      "rom.pinned-media-update-failed",
      expect.anything(),
    );
  });

  it("resets to the default selection", async () => {
    update.mockResolvedValue({} as never);
    const rom = makeRom(["file:9"]);
    const { resetPins } = usePinnedMedia(rom);

    resetPins();
    expect(rom.rom_user.pinned_media).toBeNull();
    await settle();
    expect(update).toHaveBeenCalledWith({
      romId: 3,
      data: { pinned_media: null },
    });
  });
});
