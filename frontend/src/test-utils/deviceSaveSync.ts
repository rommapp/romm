import { vi } from "vitest";

// Stands in for `@/v2/utils/saveSync` via `vi.mock(path, () => import(...))`,
// for suites that drive a player; the sync logic has its own suite.
export const PLAYER_SAVE_POLL_MS = 5000;

export const saveSyncMocks = {
  /** The constructor arguments of the latest instance. */
  args: [] as unknown[],
  capture: vi.fn(),
  captureOnUnload: vi.fn(),
  prepare: vi.fn(),
  push: vi.fn(),
  pushOnUnload: vi.fn(),
};

export class DeviceSaveSync {
  constructor(...args: unknown[]) {
    saveSyncMocks.args = args;
  }
  capture = saveSyncMocks.capture;
  captureOnUnload = saveSyncMocks.captureOnUnload;
  prepare = saveSyncMocks.prepare;
  push = saveSyncMocks.push;
  pushOnUnload = saveSyncMocks.pushOnUnload;
}
