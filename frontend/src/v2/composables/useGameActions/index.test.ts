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
const canPlayJsDos = { value: false };
const canPlayRuffle = { value: false };
const streamContainer = { value: null as object | null };
const joinableSession = {
  value: null as { host_username: string | null } | null,
};
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
    joinableForRom: () => joinableSession.value,
    fetchJoinableSessions: vi.fn(),
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
  // Mirrors the real composable: streaming needs both a container for the
  // platform and a file behind the rom.
  useCanPlay: (getRom: () => SimpleRom | null | undefined) => ({
    canPlayEJS,
    canPlayJsDos,
    canPlayRuffle,
    canPlayStream: {
      get value() {
        return (
          Boolean(getRom()?.has_file_on_disk) && streamContainer.value !== null
        );
      },
    },
  }),
}));
vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ copy: vi.fn() }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmFn,
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({
    syncCachedRom: vi.fn(),
    applyRomWrite: vi.fn(),
    refreshAfterUserStateChange: vi.fn(),
    refreshIfOrderedBy: vi.fn(),
  }),
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
    has_file_on_disk: true,
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
  canPlayJsDos.value = false;
  canPlayRuffle.value = false;
  streamContainer.value = null;
  joinableSession.value = null;
  grantedActions.value = null;
});

describe("useGameActions.joinStream", () => {
  beforeEach(() => {
    streamContainer.value = { host: "http://stream" };
    joinableSession.value = { host_username: "ada" };
  });

  it("does not navigate until the user confirms", async () => {
    confirmFn.mockResolvedValue(false);
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });

  it("navigates with the join intent once confirmed", async () => {
    confirmFn.mockResolvedValue(true);
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(push).toHaveBeenCalledWith("/rom/1/stream?join=1");
  });

  it("names the host in the confirmation", async () => {
    confirmFn.mockResolvedValue(false);
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn.mock.calls[0][0].title).toBe("rom.confirm-join-title-of");
  });

  it("falls back to an unnamed prompt when the host is unknown", async () => {
    joinableSession.value = { host_username: null };
    confirmFn.mockResolvedValue(false);
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn.mock.calls[0][0].title).toBe("rom.confirm-join-title");
  });

  it("asks nothing when there is no session to join", async () => {
    joinableSession.value = null;
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });
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

  it("goes to EmulatorJS when asked for the local player, stream or not", async () => {
    // The whole point of the two buttons: a platform both can run must still
    // be reachable in the browser.
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    await actions.play("local");

    expect(locationAssign).toHaveBeenCalledWith("/rom/1/ejs");
    expect(push).not.toHaveBeenCalled();
  });

  it("goes to the stream when asked for it", async () => {
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    await actions.play("stream");

    expect(push).toHaveBeenCalledWith("/rom/1/stream");
    expect(locationAssign).not.toHaveBeenCalled();
  });

  it("launches nothing when the asked-for player cannot run it", async () => {
    const actions = useGameActions(() => makeRom());

    await actions.play("stream");

    expect(push).not.toHaveBeenCalled();
    expect(locationAssign).not.toHaveBeenCalled();
  });

  it("still confirms a shelved game whichever player is asked for", async () => {
    confirmFn.mockResolvedValue(false);
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom("retired"));

    await actions.play("stream");

    expect(confirmFn).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });

  it("keeps SPA navigation for Ruffle", async () => {
    canPlayEJS.value = false;
    canPlayRuffle.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/ruffle");
    expect(locationAssign).not.toHaveBeenCalled();
  });

  it("full-loads js-dos ahead of EmulatorJS for its platforms", async () => {
    canPlayJsDos.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(locationAssign).toHaveBeenCalledWith("/rom/1/jsdos");
    expect(push).not.toHaveBeenCalled();
  });

  it("offers neither streaming nor download without a file behind the rom", () => {
    streamContainer.value = {};
    const fileless = { ...makeRom(), has_file_on_disk: false } as SimpleRom;
    const actions = useGameActions(() => fileless);

    expect(actions.canPlayStream.value).toBe(false);
    expect(actions.canDownload.value).toBe(false);
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
  // gates on ROMS_WRITE) would 403, so the menu must not offer it.
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
