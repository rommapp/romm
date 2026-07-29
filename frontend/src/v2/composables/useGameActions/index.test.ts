import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import type { ActionKey } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import { useGameActions } from "./index";

// Controllable stubs shared with the mocked modules below.
const push = vi.fn();
const locationAssign = vi.fn();
const confirmFn = vi.fn();
const confirmProtectedLaunch = { value: true };
const canPlayEJS = { value: true };
const canPlayRuffle = { value: false };
const streamContainer = { value: null as object | null };
let originalLocation: Location;
// Granted action keys — `null` means "everything" (the default).
const grantedActions: { value: Set<ActionKey> | null } = { value: null };

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
  useStreamingStore: () => ({
    containerForPlatform: () => streamContainer.value,
  }),
}));
vi.mock("@/utils", () => ({
  getDownloadLink: vi.fn(),
  getDownloadPath: vi.fn(),
  isNintendoDSRom: () => false,
}));
vi.mock("@/v2/composables/useCan", () => ({
  useCan: (action: ActionKey) => ({
    get value() {
      return grantedActions.value?.has(action) ?? true;
    },
  }),
}));
vi.mock("@/v2/composables/useCanPlay", () => ({
  useCanPlay: () => ({ canPlayEJS, canPlayRuffle }),
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

beforeAll(() => {
  originalLocation = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...originalLocation, assign: locationAssign },
  });
});

afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

beforeEach(() => {
  push.mockClear();
  locationAssign.mockClear();
  confirmFn.mockClear();
  confirmProtectedLaunch.value = true;
  canPlayEJS.value = true;
  canPlayRuffle.value = false;
  streamContainer.value = null;
  grantedActions.value = null;
});

describe("useGameActions.play — launch confirmation", () => {
  it("launches a normal game without confirming", async () => {
    const actions = useGameActions(() => makeRom(null));
    await actions.play();
    expect(confirmFn).not.toHaveBeenCalled();
    expect(locationAssign).toHaveBeenCalledWith("/rom/1/ejs");
    expect(push).not.toHaveBeenCalled();
  });

  it.each(["retired", "never_playing"] as const)(
    "asks before launching a %s game and aborts on cancel",
    async (status) => {
      confirmFn.mockResolvedValue(false);
      const actions = useGameActions(() => makeRom(status));
      await actions.play();
      expect(confirmFn).toHaveBeenCalledTimes(1);
      expect(locationAssign).not.toHaveBeenCalled();
      expect(push).not.toHaveBeenCalled();
    },
  );

  it("launches a shelved game once the user confirms", async () => {
    confirmFn.mockResolvedValue(true);
    const actions = useGameActions(() => makeRom("retired"));
    await actions.play();
    expect(confirmFn).toHaveBeenCalledTimes(1);
    expect(locationAssign).toHaveBeenCalledWith("/rom/1/ejs");
    expect(push).not.toHaveBeenCalled();
  });

  it("skips the prompt when the preference is disabled", async () => {
    confirmProtectedLaunch.value = false;
    const actions = useGameActions(() => makeRom("never_playing"));
    await actions.play();
    expect(confirmFn).not.toHaveBeenCalled();
    expect(locationAssign).toHaveBeenCalledWith("/rom/1/ejs");
    expect(push).not.toHaveBeenCalled();
  });

  it("prefers streaming over EmulatorJS", async () => {
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/stream");
    expect(locationAssign).not.toHaveBeenCalled();
  });

  it("keeps SPA navigation for Ruffle", async () => {
    canPlayEJS.value = false;
    canPlayRuffle.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/ruffle");
    expect(locationAssign).not.toHaveBeenCalled();
  });
});

describe("useGameActions — write/destructive gates", () => {
  it("exposes every write action when the grants allow it", () => {
    const actions = useGameActions(() => makeRom());
    expect(actions.canEdit.value).toBe(true);
    expect(actions.canDelete.value).toBe(true);
    expect(actions.canMatch.value).toBe(true);
    expect(actions.canRefresh.value).toBe(true);
  });

  it("denies them for a read-only user", () => {
    grantedActions.value = new Set<ActionKey>([
      "rom.view",
      "rom.play",
      "rom.download",
      "rom.favorite",
    ]);
    const actions = useGameActions(() => makeRom());
    expect(actions.canEdit.value).toBe(false);
    expect(actions.canDelete.value).toBe(false);
    expect(actions.canMatch.value).toBe(false);
    expect(actions.canRefresh.value).toBe(false);
  });

  it("hides delete when only the write grants are held", () => {
    grantedActions.value = new Set<ActionKey>([
      "rom.edit",
      "rom.match",
      "rom.refresh",
    ]);
    const actions = useGameActions(() => makeRom());
    expect(actions.canEdit.value).toBe(true);
    expect(actions.canDelete.value).toBe(false);
  });

  // A bare DELETE grant projects to no scope, so `POST /roms/delete` (which
  // gates on ROMS_WRITE) would 403 and the interceptor would log the user out.
  it("hides delete when the delete grant is held without the write grant", () => {
    grantedActions.value = new Set<ActionKey>(["rom.view", "rom.delete"]);
    const actions = useGameActions(() => makeRom());
    expect(actions.canDelete.value).toBe(false);
  });

  it("shows delete when both the delete and write grants are held", () => {
    grantedActions.value = new Set<ActionKey>(["rom.delete", "rom.edit"]);
    const actions = useGameActions(() => makeRom());
    expect(actions.canDelete.value).toBe(true);
  });
});
