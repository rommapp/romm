import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import GameActionsList from "./GameActionsList.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

type Flags = {
  canPlayInBrowser: boolean;
  canPlayStream: boolean;
  canShareQR: boolean;
  canOpenInFlashpoint: boolean;
  canManageCollections: boolean;
  canRemoveFromContinuePlaying: boolean;
  canMatch: boolean;
  canRefresh: boolean;
  canEdit: boolean;
  canDelete: boolean;
  canJoinStream: boolean;
  canDownload: boolean;
  canPlayNative: boolean;
  nativeLaunching: boolean;
};

// Not flags: the Join, Stream and Native items render these labels verbatim, so
// they are held apart from the booleans rather than squeezed into them. How the
// labels themselves are chosen is useGameActions' own test.
let joinActionLabel = "";
let streamActionLabel = "";
let nativeActionLabel = "";

const flags: Flags = {
  canPlayInBrowser: true,
  canPlayStream: false,
  canDownload: true,
  canShareQR: false,
  canOpenInFlashpoint: false,
  canManageCollections: true,
  canRemoveFromContinuePlaying: false,
  canMatch: true,
  canRefresh: true,
  canEdit: true,
  canDelete: true,
  canJoinStream: false,
  canPlayNative: false,
  nativeLaunching: false,
};

vi.mock("@/v2/composables/useGameActions", () => ({
  useGameActions: () =>
    new Proxy(
      {},
      {
        get(_target, prop: string) {
          if (prop in flags) {
            return {
              get value() {
                return flags[prop as keyof Flags];
              },
            };
          }
          if (prop === "isFavorited") return { value: false };
          if (prop === "joinActionLabel") return { value: joinActionLabel };
          if (prop === "streamActionLabel") return { value: streamActionLabel };
          if (prop === "nativeActionLabel") return { value: nativeActionLabel };
          return vi.fn();
        },
      },
    ),
}));

const RMenuItem = {
  props: ["label"],
  template: `<li class="item">{{ label }}</li>`,
};
const RDivider = { template: `<hr class="divider" />` };

function mountList(
  overrides: Partial<Flags> = {},
  joinLabel = "rom.join-session",
  streamLabel = "rom.stream",
  nativeLabel = "rom.play-native",
) {
  Object.assign(flags, overrides);
  joinActionLabel = joinLabel;
  streamActionLabel = streamLabel;
  nativeActionLabel = nativeLabel;
  return mount(GameActionsList, {
    props: { rom: { id: 1 } as SimpleRom },
    global: { stubs: { RMenuItem, RDivider } },
  });
}

function labels(wrapper: ReturnType<typeof mountList>) {
  return wrapper.findAll(".item").map((w) => w.text());
}

describe("GameActionsList: permission gating", () => {
  it("offers the write and destructive actions to a user who holds them", () => {
    const wrapper = mountList({
      canMatch: true,
      canRefresh: true,
      canEdit: true,
      canDelete: true,
    });
    expect(labels(wrapper)).toEqual(
      expect.arrayContaining([
        "rom.match-rom",
        "rom.refresh-metadata",
        "rom.refresh-files",
        "common.edit",
        "common.delete",
      ]),
    );
  });

  it("hides them (and their dividers) from a read-only user", () => {
    const wrapper = mountList({
      canMatch: false,
      canRefresh: false,
      canEdit: false,
      canDelete: false,
    });
    const shown = labels(wrapper);
    expect(shown).not.toContain("rom.match-rom");
    expect(shown).not.toContain("rom.refresh-metadata");
    expect(shown).not.toContain("rom.refresh-files");
    expect(shown).not.toContain("common.edit");
    expect(shown).not.toContain("common.delete");
    // Only the divider between the primary and per-user groups survives.
    expect(wrapper.findAll(".divider")).toHaveLength(1);
    // Read-only users keep the actions they can actually perform.
    expect(shown).toContain("rom.download");
    expect(shown).toContain("rom.add-to-favorites");
  });

  it("drops the download actions when no file backs the rom", () => {
    const wrapper = mountList({ canDownload: false });
    const shown = labels(wrapper);
    expect(shown).not.toContain("rom.download");
    expect(shown).not.toContain("rom.copy-link");
  });

  it("keeps the metadata divider when only some metadata actions are held", () => {
    const wrapper = mountList({
      canMatch: false,
      canRefresh: false,
      canEdit: true,
      canDelete: false,
    });
    expect(labels(wrapper)).toContain("common.edit");
    expect(wrapper.findAll(".divider")).toHaveLength(2);
  });
});

describe("GameActionsList: playing", () => {
  it("offers each way to play the caller is allowed", () => {
    const wrapper = mountList({ canPlayInBrowser: true, canPlayStream: true });
    const shown = labels(wrapper);
    expect(shown).toContain("rom.play");
    expect(shown).toContain("rom.stream");
  });

  // The button says "Play" and launches natively inside the shell, so an
  // unqualified "Play" here would read as a duplicate of it.
  it("names the browser route once the native launch owns Play", () => {
    const shown = labels(
      mountList({ canPlayInBrowser: true, canPlayNative: true }),
    );
    expect(shown).toContain("rom.play-in-browser");
    expect(shown).not.toContain("rom.play");
  });

  it("renders the stream label the composable resolved", () => {
    const wrapper = mountList(
      { canPlayInBrowser: false, canPlayStream: true },
      "rom.join-session",
      "rom.stream-on",
    );
    const shown = labels(wrapper);
    expect(shown).toContain("rom.stream-on");
    expect(shown).not.toContain("rom.play");
  });

  it("offers none of them when the ROM cannot be played", () => {
    const shown = labels(
      mountList({
        canPlayInBrowser: false,
        canPlayStream: false,
        canPlayNative: false,
      }),
    );
    expect(shown).not.toContain("rom.play");
    expect(shown).not.toContain("rom.stream");
    expect(shown).not.toContain("rom.stream-on");
    expect(shown).not.toContain("rom.play-native");
  });
});

describe("GameActionsList: playing in a local emulator", () => {
  it("renders the native label the composable resolved", () => {
    const wrapper = mountList(
      { canPlayNative: true, nativeLaunching: false },
      "rom.join-session",
      "rom.stream",
      "rom.play-native-in",
    );
    const shown = labels(wrapper);
    expect(shown).toContain("rom.play-native-in");
    expect(shown).not.toContain("rom.native-cancel");
  });

  it("swaps the launch for a cancel while one is in flight", () => {
    const shown = labels(
      mountList({ canPlayNative: true, nativeLaunching: true }),
    );
    expect(shown).toContain("rom.native-cancel");
    expect(shown).not.toContain("rom.play-native");
  });

  it("offers nothing native outside the desktop shell", () => {
    const shown = labels(
      mountList({ canPlayNative: false, nativeLaunching: false }),
    );
    expect(shown).not.toContain("rom.play-native");
    expect(shown).not.toContain("rom.native-cancel");
  });
});

describe("GameActionsList: joining someone else's session", () => {
  it("renders the join label the composable resolved", () => {
    const wrapper = mountList({ canJoinStream: true }, "rom.join-session-of");
    expect(labels(wrapper)).toContain("rom.join-session-of");
  });

  it("offers nothing to join when no session is open", () => {
    const shown = labels(mountList({ canJoinStream: false }, "ana"));
    expect(shown).not.toContain("rom.join-session");
    expect(shown).not.toContain("rom.join-session-of");
  });
});
