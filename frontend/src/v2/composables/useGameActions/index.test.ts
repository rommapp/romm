import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import { useGameActions } from "./index";

// Controllable stubs shared with the mocked modules below.
const push = vi.fn();
const confirmFn = vi.fn();
const confirmProtectedLaunch = { value: true };

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
}));
vi.mock("@/composables/useFavoriteToggle", () => ({
  useFavoriteToggle: () => ({
    isFavorite: () => false,
    toggleFavorite: vi.fn(),
  }),
}));
vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({ confirmProtectedLaunch }),
}));
vi.mock("@/services/api/rom", () => ({
  default: { updateUserRomProps: vi.fn() },
}));
vi.mock("@/stores/auth", () => ({
  default: () => ({ scopes: [] as string[] }),
}));
vi.mock("@/stores/roms", () => ({
  default: () => ({ update: vi.fn(), removeFromContinuePlaying: vi.fn() }),
}));
vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({ containerForPlatform: () => null }),
}));
vi.mock("@/utils", () => ({
  getDownloadLink: vi.fn(),
  getDownloadPath: vi.fn(),
  isNintendoDSRom: () => false,
}));
vi.mock("@/v2/composables/useCan", () => ({
  useCan: () => ({ value: true }),
}));
// EJS is the only playable core in these tests, so play() routes to /ejs.
vi.mock("@/v2/composables/useCanPlay", () => ({
  useCanPlay: () => ({
    canPlayEJS: { value: true },
    canPlayRuffle: { value: false },
  }),
}));
vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ copy: vi.fn() }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmFn,
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));
vi.mock("@/v2/composables/useViewTransition", () => ({
  useViewTransition: () => ({
    morphTransition: (_opts: unknown, cb: () => void) => cb(),
  }),
}));

function makeRom(status: SimpleRom["rom_user"]["status"] = null): SimpleRom {
  return {
    id: 1,
    name: "Chrono Trigger",
    fs_name_no_ext: "Chrono Trigger",
    platform_slug: "snes",
    rom_user: { status },
  } as unknown as SimpleRom;
}

beforeEach(() => {
  push.mockClear();
  confirmFn.mockClear();
  confirmProtectedLaunch.value = true;
});

describe("useGameActions.play — launch confirmation", () => {
  it("launches a normal game without confirming", async () => {
    const actions = useGameActions(() => makeRom(null));
    await actions.play();
    expect(confirmFn).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/rom/1/ejs");
  });

  it.each(["retired", "never_playing"] as const)(
    "asks before launching a %s game and aborts on cancel",
    async (status) => {
      confirmFn.mockResolvedValue(false);
      const actions = useGameActions(() => makeRom(status));
      await actions.play();
      expect(confirmFn).toHaveBeenCalledTimes(1);
      expect(push).not.toHaveBeenCalled();
    },
  );

  it("launches a shelved game once the user confirms", async () => {
    confirmFn.mockResolvedValue(true);
    const actions = useGameActions(() => makeRom("retired"));
    await actions.play();
    expect(confirmFn).toHaveBeenCalledTimes(1);
    expect(push).toHaveBeenCalledWith("/rom/1/ejs");
  });

  it("skips the prompt when the preference is disabled", async () => {
    confirmProtectedLaunch.value = false;
    const actions = useGameActions(() => makeRom("never_playing"));
    await actions.play();
    expect(confirmFn).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/rom/1/ejs");
  });
});
