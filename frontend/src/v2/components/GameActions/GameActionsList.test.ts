import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
  canAddToSteam: boolean;
};

// Not flags: the Join and Stream items render these labels verbatim, so they
// are held apart from the booleans rather than squeezed into them. How the
// labels themselves are chosen is useGameActions' own test.
let joinActionLabel = "";
let streamActionLabel = "";

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
  canAddToSteam: false,
};

interface TestSteamTarget {
  device: { id: string };
  shortcut: { status: string } | null;
  supported: boolean | null;
}

let steamTargets: TestSteamTarget[] = [];
const toggleSteam = vi.fn();

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
          if (prop === "steamTargets") return { value: steamTargets };
          if (prop === "steamTargetLabel")
            return (t: { device: { id: string } }) => `steam:${t.device.id}`;
          if (prop === "steamTargetDisabled")
            return (t: { supported: boolean | null }) => t.supported === false;
          if (prop === "toggleSteam") return toggleSteam;
          if (prop === "joinActionLabel") return { value: joinActionLabel };
          if (prop === "streamActionLabel") return { value: streamActionLabel };
          return vi.fn();
        },
      },
    ),
}));

const RMenuItem = {
  props: ["label", "disabled", "variant"],
  emits: ["click"],
  template: `<li class="item" :data-disabled="disabled" :data-variant="variant" @click="$emit('click')">{{ label }}</li>`,
};
const RDivider = { template: `<hr class="divider" />` };

beforeEach(() => {
  steamTargets = [];
  toggleSteam.mockClear();
});

function mountList(
  overrides: Partial<Flags> = {},
  joinLabel = "rom.join-session",
  streamLabel = "rom.stream",
) {
  Object.assign(flags, overrides);
  joinActionLabel = joinLabel;
  streamActionLabel = streamLabel;
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

describe("GameActionsList: Steam", () => {
  const target = (
    id: string,
    shortcut: { status: string } | null = null,
    supported: boolean | null = true,
  ) => ({ device: { id }, shortcut, supported });

  it("lists one row per companion", () => {
    steamTargets = [target("pc"), target("laptop")];
    const wrapper = mountList({ canAddToSteam: true });
    expect(labels(wrapper)).toEqual(
      expect.arrayContaining(["steam:pc", "steam:laptop"]),
    );
  });

  it("shows no rows when the user cannot add to Steam", () => {
    steamTargets = [target("pc")];
    const wrapper = mountList({ canAddToSteam: false });
    expect(labels(wrapper)).not.toContain("steam:pc");
  });

  it("disables a companion that cannot play the platform", () => {
    steamTargets = [target("pc", null, false)];
    const wrapper = mountList({ canAddToSteam: true });
    const row = wrapper.findAll(".item").find((i) => i.text() === "steam:pc");
    expect(row?.attributes("data-disabled")).toBe("true");
  });

  it("marks a game already in Steam as active", () => {
    steamTargets = [target("pc", { status: "added" })];
    const wrapper = mountList({ canAddToSteam: true });
    const row = wrapper.findAll(".item").find((i) => i.text() === "steam:pc");
    expect(row?.attributes("data-variant")).toBe("active");
  });

  it("dispatches the toggle for the row that was clicked", async () => {
    steamTargets = [target("pc"), target("laptop")];
    const wrapper = mountList({ canAddToSteam: true });
    const row = wrapper
      .findAll(".item")
      .find((i) => i.text() === "steam:laptop");
    await row?.trigger("click");
    expect(toggleSteam).toHaveBeenCalledTimes(1);
    expect(toggleSteam.mock.calls[0][0].device.id).toBe("laptop");
  });
});
