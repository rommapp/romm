import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ActionKey } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import { makeRom as baseRom } from "@/utils/rom.fixtures";
import { useGameActions } from "./index";

// Controllable stubs shared with the mocked modules below.
const push = vi.fn();
const confirmFn = vi.fn();
const startScan = vi.fn(() => true);
const snackbarInfo = vi.fn();
const snackbarError = vi.fn();
const probeFormatDownload = vi.fn();
const downloadRom = vi.fn();
const confirmProtectedLaunch = { value: true };
const canPlayEJS = { value: true };
const canPlayJsDos = { value: false };
const canPlayPico8 = { value: false };
const canPlayEasyRpg = { value: false };
const canPlayRuffle = { value: false };
const canPlayNative = { value: false };
const streamContainer = { value: null as object | null };
const joinableSession = {
  value: null as { host_username: string | null; container?: string } | null,
};
const grantedActions: { value: Set<ActionKey> | null } = { value: null };
const { clipboardCopy, emitterEmit } = vi.hoisted(() => ({
  clipboardCopy: vi.fn(),
  emitterEmit: vi.fn(),
}));

vi.mock("vue", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue")>()),
  inject: () => ({ emit: emitterEmit }),
}));
vi.mock("vue-i18n");
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
  default: {
    updateUserRomProps: vi.fn(),
    probeFormatDownload: (href: string) => probeFormatDownload(href),
    downloadRom: (opts: unknown) => downloadRom(opts),
  },
}));

const authScopes: string[] = [];
const deviceInstall = {
  ENABLED: true,
  EXCLUDED_PLATFORM_SLUGS: ["win"] as string[],
};

vi.mock("@/stores/auth", () => ({
  default: () => ({ scopes: authScopes }),
}));
vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ value: { DEVICE_INSTALL: deviceInstall } }),
}));
vi.mock("@/stores/roms", () => ({
  default: () => ({ update: vi.fn(), removeFromContinuePlaying: vi.fn() }),
}));
vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({
    containerForPlatform: () => streamContainer.value,
    containerLabelForPlatform: () => {
      const c = streamContainer.value as {
        label?: string;
        emulator?: string;
      } | null;
      return c ? c.label || c.emulator || null : null;
    },
    joinableForRom: () => joinableSession.value,
    fetchJoinableSessions: vi.fn(),
  }),
}));
vi.mock("@/utils", async () => {
  const actual = await vi.importActual<typeof import("@/utils/downloadPath")>(
    "@/utils/downloadPath",
  );
  return {
    getDownloadLink: vi.fn(
      () => "http://romm.local/api/roms/1/content/game.zip",
    ),
    getDownloadPath: vi.fn(() => "/api/roms/1/content/game.chd?format=iso"),
    getSoleRomFile: actual.getSoleRomFile,
    isNintendoDSRom: () => false,
  };
});
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
    canPlayPico8,
    canPlayEasyRpg,
    canPlayRuffle,
    canPlayNative,
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
  useClipboard: () => ({ copy: clipboardCopy }),
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
vi.mock("@/v2/composables/useScanTrigger", () => ({
  useScanTrigger: () => ({ startScan }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: vi.fn(),
    error: snackbarError,
    info: snackbarInfo,
  }),
}));
vi.mock("@/v2/composables/useViewTransition", () => ({
  useViewTransition: () => ({
    morphTransition: (_opts: unknown, cb: () => void) => cb(),
  }),
}));

function makeRom(status: SimpleRom["rom_user"]["status"] = null): SimpleRom {
  return baseRom({
    name: "Chrono Trigger",
    fs_name_no_ext: "Chrono Trigger",
    platform_slug: "snes",
    has_file_on_disk: true,
    rom_user: { status } as SimpleRom["rom_user"],
  });
}

beforeEach(() => {
  probeFormatDownload.mockReset();
  downloadRom.mockReset();
  clipboardCopy.mockReset();
  emitterEmit.mockReset();
  confirmProtectedLaunch.value = true;
  canPlayEJS.value = true;
  canPlayJsDos.value = false;
  canPlayPico8.value = false;
  canPlayEasyRpg.value = false;
  canPlayRuffle.value = false;
  canPlayNative.value = false;
  streamContainer.value = null;
  joinableSession.value = null;
  grantedActions.value = null;
  authScopes.splice(0, authScopes.length);
  deviceInstall.ENABLED = true;
});

describe("useGameActions.canInstallOnDevice", () => {
  beforeEach(() => {
    authScopes.push("devices.read", "devices.write", "roms.read");
  });

  it("offers the install for a rom with files on an allowed platform", () => {
    const actions = useGameActions(() => makeRom());

    expect(actions.canInstallOnDevice.value).toBe(true);
  });

  it("hides it for an excluded platform", () => {
    const rom = { ...makeRom(), platform_slug: "win" } as SimpleRom;
    const actions = useGameActions(() => rom);

    expect(actions.canInstallOnDevice.value).toBe(false);
  });

  it("hides it while the server has the feature off", () => {
    deviceInstall.ENABLED = false;
    const actions = useGameActions(() => makeRom());

    expect(actions.canInstallOnDevice.value).toBe(false);
  });

  it("hides it from a caller without the devices.write scope", () => {
    authScopes.splice(0, authScopes.length, "devices.read", "roms.read");
    const actions = useGameActions(() => makeRom());

    expect(actions.canInstallOnDevice.value).toBe(false);
  });

  it("hides it from a caller without the devices.read scope", () => {
    authScopes.splice(0, authScopes.length, "devices.write", "roms.read");
    const actions = useGameActions(() => makeRom());

    expect(actions.canInstallOnDevice.value).toBe(false);
  });
});

describe("useGameActions.joinStream", () => {
  beforeEach(() => {
    streamContainer.value = { host: "http://stream" };
    joinableSession.value = {
      host_username: "ada",
      container: "http://box:8000",
    };
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

    // The joinable row names the container, and a pool needs it: the stream
    // view would otherwise walk the pool and could land on another session.
    expect(push).toHaveBeenCalledWith(
      "/rom/1/stream?join=1&container=http%3A%2F%2Fbox%3A8000",
    );
  });

  it("names the host in the confirmation", async () => {
    confirmFn.mockResolvedValue(false);
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn.mock.calls[0]![0].title).toBe(
      'rom.confirm-join-title-of:{"user":"ada"}',
    );
  });

  it("falls back to an unnamed prompt when the host is unknown", async () => {
    joinableSession.value = { host_username: null };
    confirmFn.mockResolvedValue(false);
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn.mock.calls[0]![0].title).toBe("rom.confirm-join-title");
  });

  it("asks nothing when there is no session to join", async () => {
    joinableSession.value = null;
    const actions = useGameActions(() => makeRom());

    await actions.joinStream();

    expect(confirmFn).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });
});

describe("useGameActions — stream and join action labels", () => {
  // Both the action button and the overflow menu render these verbatim, so the
  // fallback rule is tested once here rather than in each surface.
  it("names the container a stream would run on", () => {
    streamContainer.value = { label: "Dreamcast box", emulator: "flycast" };
    const actions = useGameActions(() => makeRom());

    expect(actions.streamActionLabel.value).toBe(
      'rom.stream-on:{"container":"Dreamcast box"}',
    );
  });

  it("says only 'stream' when no container is configured", () => {
    streamContainer.value = null;
    const actions = useGameActions(() => makeRom());

    expect(actions.streamActionLabel.value).toBe("rom.stream");
  });

  it("names the host of a session that advertises one", () => {
    streamContainer.value = { host: "http://stream" };
    joinableSession.value = { host_username: "ada" };
    const actions = useGameActions(() => makeRom());

    expect(actions.joinActionLabel.value).toBe(
      'rom.join-session-of:{"user":"ada"}',
    );
  });

  it("falls back to the plain join label when the host is unknown", () => {
    streamContainer.value = { host: "http://stream" };
    joinableSession.value = { host_username: null };
    const actions = useGameActions(() => makeRom());

    expect(actions.joinActionLabel.value).toBe("rom.join-session");
  });
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

  it("prefers streaming over EmulatorJS", async () => {
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/stream");
  });

  it("goes to EmulatorJS when asked for the local player, stream or not", async () => {
    // The whole point of the two buttons: a platform both can run must still
    // be reachable in the browser.
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    await actions.play("local");

    expect(push).toHaveBeenCalledWith("/rom/1/ejs");
  });

  it("goes to the stream when asked for it", async () => {
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    await actions.play("stream");

    expect(push).toHaveBeenCalledWith("/rom/1/stream");
  });

  it("launches nothing when the asked-for player cannot run it", async () => {
    const actions = useGameActions(() => makeRom());

    await actions.play("stream");

    expect(push).not.toHaveBeenCalled();
  });

  it("still confirms a shelved game whichever player is asked for", async () => {
    confirmFn.mockResolvedValue(false);
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom("retired"));

    await actions.play("stream");

    expect(confirmFn).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });

  it("goes to Ruffle for a Flash rom", async () => {
    canPlayEJS.value = false;
    canPlayRuffle.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/ruffle");
  });

  it("goes to PICO-8 for a cartridge", async () => {
    canPlayEJS.value = false;
    canPlayPico8.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/pico8");
  });

  it("goes to EasyRPG for an RPG Maker game", async () => {
    canPlayEJS.value = false;
    canPlayEasyRpg.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/easyrpg");
  });

  it("prefers js-dos over EmulatorJS for its platforms", async () => {
    canPlayJsDos.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/jsdos");
  });

  it("opens the play page for a platform only the desktop shell can run", async () => {
    canPlayEJS.value = false;
    canPlayNative.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/ejs");
  });

  // The shell's emulator is offered from the same page a core plays on, so
  // where both can run the game there is still one route to open.
  it("opens the same page when a core can run it too", async () => {
    canPlayNative.value = true;
    const actions = useGameActions(() => makeRom());

    await actions.play();

    expect(push).toHaveBeenCalledWith("/rom/1/ejs");
  });

  it("offers the Play button wherever either route can run the game", () => {
    canPlayEJS.value = false;
    expect(useGameActions(() => makeRom()).canPlayLocally.value).toBe(false);
    canPlayNative.value = true;
    expect(useGameActions(() => makeRom()).canPlayLocally.value).toBe(true);
  });

  it("offers neither streaming nor download without a file behind the rom", () => {
    streamContainer.value = {};
    const fileless = { ...makeRom(), has_file_on_disk: false } as SimpleRom;
    const actions = useGameActions(() => fileless);

    expect(actions.canPlayStream.value).toBe(false);
    expect(actions.canDownload.value).toBe(false);
  });
});

describe("useGameActions.needsLaunchConfirm", () => {
  it.each(["retired", "never_playing"] as const)(
    "asks before launching a %s game",
    (status) => {
      expect(
        useGameActions(() => makeRom(status)).needsLaunchConfirm.value,
      ).toBe(true);
    },
  );

  it("asks nothing for a game that is not shelved", () => {
    expect(useGameActions(() => makeRom()).needsLaunchConfirm.value).toBe(
      false,
    );
  });

  it("asks nothing when the preference is disabled", () => {
    confirmProtectedLaunch.value = false;
    expect(
      useGameActions(() => makeRom("retired")).needsLaunchConfirm.value,
    ).toBe(false);
  });
});

describe("useGameActions.playPath", () => {
  it("points the local launch at EmulatorJS", () => {
    const actions = useGameActions(() => makeRom());

    expect(actions.playPath("local")).toBe("/rom/1/ejs");
    expect(actions.playPath()).toBe("/rom/1/ejs");
  });

  it("prefers the stream only when nobody asked for the local player", () => {
    streamContainer.value = {};
    const actions = useGameActions(() => makeRom());

    expect(actions.playPath()).toBe("/rom/1/stream");
    expect(actions.playPath("stream")).toBe("/rom/1/stream");
    expect(actions.playPath("local")).toBe("/rom/1/ejs");
  });

  it("has nowhere to go when the asked-for player cannot run the rom", () => {
    const actions = useGameActions(() => makeRom());

    expect(actions.playPath("stream")).toBeNull();
  });

  it("orders the in-browser players the way play() launches them", () => {
    const actions = useGameActions(() => makeRom());

    canPlayJsDos.value = true;
    expect(actions.playPath("local")).toBe("/rom/1/jsdos");

    canPlayJsDos.value = false;
    canPlayEJS.value = false;
    canPlayPico8.value = true;
    canPlayRuffle.value = true;
    expect(actions.playPath("local")).toBe("/rom/1/pico8");

    canPlayPico8.value = false;
    canPlayEasyRpg.value = true;
    expect(actions.playPath("local")).toBe("/rom/1/easyrpg");

    canPlayEasyRpg.value = false;
    expect(actions.playPath("local")).toBe("/rom/1/ruffle");
  });

  it("resolves nothing without a rom", () => {
    const actions = useGameActions(() => null);

    expect(actions.playPath()).toBeNull();
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

describe("useGameActions.refreshFiles", () => {
  it("refreshes the rom files without any provider", () => {
    const rom = { ...makeRom(null), platform_id: 7 } as SimpleRom;
    const actions = useGameActions(() => rom);

    actions.refreshFiles();

    expect(startScan).toHaveBeenCalledWith([
      { platforms: [7], roms_ids: [1], type: "quick", apis: [] },
    ]);
    expect(snackbarInfo).toHaveBeenCalledWith(
      'rom.refreshing-files:{"name":"Chrono Trigger"}',
      expect.anything(),
    );
  });

  it("stays quiet when a scan is already running", () => {
    startScan.mockReturnValueOnce(false);
    const actions = useGameActions(() => makeRom(null));

    actions.refreshFiles();

    expect(snackbarInfo).not.toHaveBeenCalled();
  });
});

describe("useGameActions.downloadAs", () => {
  function pspRom(
    files: { id: number; file_name: string }[],
    downloadFormats = ["cso", "iso", "zso"],
  ): SimpleRom {
    return {
      ...baseRom({
        platform_slug: "psp",
        has_file_on_disk: true,
        files: files as SimpleRom["files"],
      }),
      download_formats: downloadFormats,
    } as SimpleRom;
  }

  it("offers the formats the detailed rom lists", () => {
    const rom = pspRom([{ id: 1, file_name: "Game.CHD" }]);
    expect(useGameActions(() => rom).downloadFormats.value).toEqual([
      "cso",
      "iso",
      "zso",
    ]);
  });

  it("offers nothing for a rom without the list or without a file", () => {
    const simple = baseRom({ platform_slug: "psp", has_file_on_disk: true });
    expect(useGameActions(() => simple).downloadFormats.value).toEqual([]);

    const missing = { ...pspRom([]), has_file_on_disk: false } as SimpleRom;
    expect(useGameActions(() => missing).downloadFormats.value).toEqual([]);
  });

  it("downloads straight away when the format can be served", async () => {
    probeFormatDownload.mockResolvedValue({
      status: 206,
      retryAfterSeconds: null,
    });
    const rom = pspRom([{ id: 7, file_name: "game.chd" }]);

    await useGameActions(() => rom).downloadAs("iso");

    expect(downloadRom).toHaveBeenCalledWith({
      rom,
      fileIDs: [7],
      format: "iso",
    });
    expect(snackbarInfo).not.toHaveBeenCalled();
  });

  it("polls while it converts, then downloads", async () => {
    vi.useFakeTimers();
    probeFormatDownload
      .mockResolvedValueOnce({ status: 202, retryAfterSeconds: 5 })
      .mockResolvedValueOnce({ status: 206, retryAfterSeconds: null });
    const rom = pspRom([{ id: 7, file_name: "game.chd" }]);

    const pending = useGameActions(() => rom).downloadAs("iso");
    await vi.advanceTimersByTimeAsync(5000);
    await pending;

    expect(snackbarInfo).toHaveBeenCalledWith(
      'rom.download-as-preparing:{"format":"ISO"}',
    );
    expect(probeFormatDownload).toHaveBeenCalledTimes(2);
    expect(downloadRom).toHaveBeenCalledOnce();
  });

  it("reports a format the server refuses", async () => {
    probeFormatDownload.mockResolvedValue({
      status: 406,
      retryAfterSeconds: null,
    });
    const rom = pspRom([{ id: 7, file_name: "game.chd" }]);

    await useGameActions(() => rom).downloadAs("iso");

    expect(downloadRom).not.toHaveBeenCalled();
    expect(snackbarError).toHaveBeenCalledWith(
      'rom.download-as-unavailable:{"format":"ISO"}',
      {
        persist: { body: "Game", link: "/rom/1" },
      },
    );
  });

  it("ignores a second click while the first is still waiting", async () => {
    vi.useFakeTimers();
    probeFormatDownload
      .mockResolvedValueOnce({ status: 202, retryAfterSeconds: 5 })
      .mockResolvedValueOnce({ status: 206, retryAfterSeconds: null });
    const rom = pspRom([{ id: 7, file_name: "game.chd" }]);
    const actions = useGameActions(() => rom);

    const first = actions.downloadAs("iso");
    await actions.downloadAs("iso");
    await vi.advanceTimersByTimeAsync(5000);
    await first;

    expect(probeFormatDownload).toHaveBeenCalledTimes(2);
    expect(downloadRom).toHaveBeenCalledOnce();
  });
});

describe("useGameActions.copyDownloadLink", () => {
  const LINK = "http://romm.local/api/roms/1/content/game.zip";

  it("copies the download link with a success toast", async () => {
    await useGameActions(() => makeRom()).copyDownloadLink();

    expect(clipboardCopy).toHaveBeenCalledWith(
      LINK,
      expect.objectContaining({
        successMessage: "rom.snackbar-download-link-copied",
      }),
    );
  });

  it("opens the manual-copy dialog when the copy fails", async () => {
    clipboardCopy.mockImplementation(
      async (_text: string, opts: { fallback?: () => void }) => {
        opts.fallback?.();
        return false;
      },
    );

    await useGameActions(() => makeRom()).copyDownloadLink();

    expect(emitterEmit).toHaveBeenCalledWith(
      "showCopyDownloadLinkDialog",
      LINK,
    );
  });
});
