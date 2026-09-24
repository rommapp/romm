import { mount } from "@vue/test-utils";
import mitt from "mitt";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import { installSyncConflictToast } from "./index";

// Minimal socket stand-in: records handlers so tests can fire events, and
// stays "connected" so `useSocketEvent` never tries to dial out.
const handlers = new Map<string, (payload: unknown) => void>();
vi.mock("@/services/socket", () => ({
  default: {
    connected: true,
    connect: vi.fn(),
    on: (event: string, handler: (payload: unknown) => void) => {
      handlers.set(event, handler);
    },
    off: vi.fn(),
  },
}));

// The composable only interpolates, so echoing the key and the name is enough
// to tell "named the game" from "fell back to the generic string".
vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: { game?: string }) =>
      params?.game ? `${key}:${params.game}` : key,
  }),
}));

const cachedRom = {
  id: 7,
  name: "Pokemon Violet",
  fs_name: "pokemon_violet.zip",
};
const blankNameRom = { id: 8, name: "", fs_name: "blank_name.zip" };
vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => ({
    getRomById: (id: number) =>
      [cachedRom, blankNameRom].find((rom) => rom.id === id) ?? null,
  }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ currentRom: null, recentRoms: [] }),
}));

const emitter = mitt();
let host: ReturnType<typeof mount> | null = null;

function install() {
  host = mount(
    defineComponent({
      setup() {
        installSyncConflictToast();
        return () => null;
      },
    }),
    { global: { provide: { emitter } } },
  );
}

function conflict(overrides: Record<string, unknown> = {}) {
  return {
    device_id: "dev-1",
    session_id: 3,
    file_name: "pokemon_violet.sav",
    rom_id: cachedRom.id,
    reason: "Both sides changed since last sync",
    ...overrides,
  };
}

describe("useSyncConflictToast", () => {
  let toasts: unknown[] = [];

  beforeEach(() => {
    handlers.clear();
    toasts = [];
    // The emitter outlives the tests, so stale listeners would each record the
    // same emit and inflate the counts.
    emitter.all.clear();
    emitter.on("snackbarShow", (payload) => {
      toasts.push(payload);
    });
  });

  afterEach(() => {
    host?.unmount();
    host = null;
  });

  it("warns with the game name", () => {
    install();
    handlers.get("sync:conflict")?.(conflict());

    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toMatchObject({
      color: "warning",
      msg: `rom.save-conflict-detected:${cachedRom.name}`,
    });
  });

  it("falls back to the file name when the ROM's name is blank", () => {
    install();
    handlers.get("sync:conflict")?.(conflict({ rom_id: blankNameRom.id }));

    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toMatchObject({
      msg: `rom.save-conflict-detected:${blankNameRom.fs_name}`,
    });
  });

  it("falls back to the generic string when the ROM is not cached", () => {
    install();
    handlers.get("sync:conflict")?.(conflict({ rom_id: 999 }));

    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toMatchObject({
      msg: "rom.save-conflict-detected-unknown-game",
    });
  });

  it("toasts once per conflict, however often it is reported", () => {
    install();
    const handler = handlers.get("sync:conflict");
    handler?.(conflict());
    handler?.(conflict());
    handler?.(conflict({ file_name: "another_game.sav" }));

    expect(toasts).toHaveLength(2);
  });

  it("toasts per device, so a second device's conflict is not swallowed", () => {
    install();
    const handler = handlers.get("sync:conflict");
    handler?.(conflict());
    handler?.(conflict({ device_id: "dev-2" }));

    expect(toasts).toHaveLength(2);
  });
});
