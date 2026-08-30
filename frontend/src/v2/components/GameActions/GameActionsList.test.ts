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
};

// Not flags: the Join and Stream items pick their labels off these, so they
// are held apart from the booleans rather than squeezed into them.
let joinHostLabel = "";
let streamLabel = "";

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
          if (prop === "joinHostLabel") return { value: joinHostLabel };
          if (prop === "streamLabel") return { value: streamLabel };
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
  hostLabel = "",
  stream = "",
) {
  Object.assign(flags, overrides);
  joinHostLabel = hostLabel;
  streamLabel = stream;
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

  it("names the container when the platform's stream has a label", () => {
    const wrapper = mountList(
      { canPlayInBrowser: false, canPlayStream: true },
      "",
      "Dreamcast box",
    );
    const shown = labels(wrapper);
    expect(shown).toContain("rom.stream-on");
    expect(shown).not.toContain("rom.play");
  });

  it("offers neither when the ROM cannot be played", () => {
    const shown = labels(
      mountList({ canPlayInBrowser: false, canPlayStream: false }),
    );
    expect(shown).not.toContain("rom.play");
    expect(shown).not.toContain("rom.stream");
    expect(shown).not.toContain("rom.stream-on");
  });
});

describe("GameActionsList: joining someone else's session", () => {
  it("names the host when the session advertises one", () => {
    const wrapper = mountList({ canJoinStream: true }, "ana");
    expect(labels(wrapper)).toContain("rom.join-session-of");
  });

  it("falls back to the plain label when the host is unknown", () => {
    const wrapper = mountList({ canJoinStream: true }, "");
    expect(labels(wrapper)).toContain("rom.join-session");
  });

  it("offers nothing to join when no session is open", () => {
    const shown = labels(mountList({ canJoinStream: false }, "ana"));
    expect(shown).not.toContain("rom.join-session");
    expect(shown).not.toContain("rom.join-session-of");
  });
});
