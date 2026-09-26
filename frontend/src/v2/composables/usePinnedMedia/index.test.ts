import { beforeEach, describe, expect, it, vi } from "vitest";
import { reactive, shallowRef } from "vue";
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

const auth = vi.hoisted(() => ({ scopes: ["roms.user.write"] }));
vi.mock("@/stores/auth", () => ({ default: () => auth }));

const snackbarError = vi.fn();
const syncCachedRom = vi.fn();
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ syncCachedRom }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: snackbarError }),
}));

vi.mock("@/v2/utils/pinnedMedia", () => ({
  PINNED_MEDIA_MAX_ITEMS: 3,
  pinnedMediaKeys: (rom: DetailedRom) =>
    rom.rom_user.pinned_media ?? ["file:1"],
  togglePinnedMediaKey: (keys: string[], key: string) =>
    keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key],
}));

const update = vi.mocked(romApi.updateUserRomProps);

let nextRomId = 1;

function makeRom(pinnedMedia: string[] | null): DetailedRom {
  return reactive({
    id: nextRomId++,
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

    expect(isPinned.value?.("file:1")).toBe(true);
    expect(isCustomized.value).toBe(false);

    togglePin("file:2");
    expect(rom.rom_user.pinned_media).toEqual(["file:1", "file:2"]);
    expect(isCustomized.value).toBe(true);
    await settle();
    expect(update).toHaveBeenCalledWith({
      romId: rom.id,
      data: { pinned_media: ["file:1", "file:2"] },
    });
  });

  it("sends toggles from every caller one after another, in click order", async () => {
    const releases: (() => void)[] = [];
    update.mockImplementation(
      () => new Promise((resolve) => releases.push(() => resolve({} as never))),
    );
    const rom = makeRom([]);
    const screenshots = usePinnedMedia(rom);
    const artwork = usePinnedMedia(rom);

    screenshots.togglePin("file:1");
    artwork.togglePin("file:2");
    await settle();
    expect(update).toHaveBeenCalledTimes(1);

    releases[0]();
    await settle();
    expect(update).toHaveBeenCalledTimes(2);
    expect(update.mock.calls[1][0].data).toEqual({
      pinned_media: ["file:1", "file:2"],
    });
    releases[1]();
    await settle();
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

  it("keeps a newer pin when an earlier write fails", async () => {
    update
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({} as never);
    const rom = makeRom([]);
    const { togglePin } = usePinnedMedia(rom);

    togglePin("file:1");
    togglePin("file:2");
    await settle();
    expect(rom.rom_user.pinned_media).toEqual(["file:1", "file:2"]);
    expect(snackbarError).toHaveBeenCalledOnce();
  });

  it("restores the last saved pins when every pending write fails", async () => {
    update.mockRejectedValue(new Error("offline"));
    const rom = makeRom(["file:9"]);
    const { togglePin } = usePinnedMedia(rom);

    togglePin("file:1");
    togglePin("file:2");
    await settle();
    expect(rom.rom_user.pinned_media).toEqual(["file:9"]);
  });

  it("settles on the ROM a refetch swapped in mid-write", async () => {
    update.mockResolvedValue({} as never);
    const loaded = makeRom([]);
    const current = shallowRef(loaded);
    const { togglePin } = usePinnedMedia(() => current.value);

    togglePin("file:1");
    const refetched = reactive({
      id: loaded.id,
      rom_user: { pinned_media: [] as string[] } as RomUserSchema,
    }) as DetailedRom;
    current.value = refetched;
    await settle();
    expect(refetched.rom_user.pinned_media).toEqual(["file:1"]);
  });

  it("refuses a pin past the limit without writing", async () => {
    const rom = makeRom(["file:1", "file:2", "file:3"]);
    const { togglePin } = usePinnedMedia(rom);

    togglePin("file:4");
    await settle();
    expect(rom.rom_user.pinned_media).toEqual(["file:1", "file:2", "file:3"]);
    expect(update).not.toHaveBeenCalled();
    expect(snackbarError).toHaveBeenCalledWith(
      "rom.pinned-media-limit",
      expect.anything(),
    );
  });

  it("hides pin controls without the roms.user.write scope", () => {
    auth.scopes = [];
    const { isPinned } = usePinnedMedia(makeRom(["file:1"]));

    expect(isPinned.value).toBeUndefined();
    auth.scopes = ["roms.user.write"];
  });

  it("resets to the default selection", async () => {
    update.mockResolvedValue({} as never);
    const rom = makeRom(["file:9"]);
    const { resetPins } = usePinnedMedia(rom);

    resetPins();
    expect(rom.rom_user.pinned_media).toBeNull();
    await settle();
    expect(update).toHaveBeenCalledWith({
      romId: rom.id,
      data: { pinned_media: null },
    });
  });
});
