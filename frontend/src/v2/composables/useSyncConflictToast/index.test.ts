import { mount } from "@vue/test-utils";
import mitt from "mitt";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import {
  type SyncConflictSocketPayload,
  installSyncConflictToast,
} from "./index";

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

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params: { game: string }) => `${key}:${params.game}`,
  }),
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

function conflict(
  overrides: Partial<SyncConflictSocketPayload> = {},
): SyncConflictSocketPayload {
  return {
    device_id: "dev-1",
    session_id: 3,
    file_name: "pokemon_violet.sav",
    rom_id: 7,
    rom_name: "Pokemon Violet",
    reason: "Both sides changed since last sync",
    ...overrides,
  };
}

describe("useSyncConflictToast", () => {
  let toasts: unknown[] = [];

  function fire(overrides: Partial<SyncConflictSocketPayload> = {}) {
    handlers.get("sync:conflict")?.(conflict(overrides));
  }

  beforeEach(() => {
    handlers.clear();
    toasts = [];
    // The emitter outlives the tests, so stale listeners would each record the
    // same emit and inflate the counts.
    emitter.all.clear();
    emitter.on("snackbarShow", (payload) => {
      toasts.push(payload);
    });
    install();
  });

  afterEach(() => {
    host?.unmount();
    host = null;
  });

  it("warns with the game name from the payload", () => {
    fire();

    expect(toasts).toHaveLength(1);
    expect(toasts[0]).toMatchObject({
      color: "warning",
      msg: "rom.save-conflict-detected:Pokemon Violet",
    });
  });

  it("toasts once per conflict, however often it is reported", () => {
    fire();
    fire();
    fire({ file_name: "another_game.sav" });

    expect(toasts).toHaveLength(2);
  });

  it("toasts per device, so a second device's conflict is not swallowed", () => {
    fire();
    fire({ device_id: "dev-2" });

    expect(toasts).toHaveLength(2);
  });
});
