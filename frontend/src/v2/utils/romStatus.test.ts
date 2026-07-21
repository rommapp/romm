import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RomUserSchema } from "@/__generated__";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import { applyLaunchStatus, recordLaunch } from "./romStatus";

vi.mock("@/services/api/rom", () => ({
  default: { updateUserRomProps: vi.fn() },
}));

const updateUserRomProps = vi.mocked(romApi.updateUserRomProps);

// Minimal RomUserSchema factory — only the fields the launch helpers read
// matter, the rest are filled with representative defaults.
function makeRomUser(overrides: Partial<RomUserSchema> = {}): RomUserSchema {
  return {
    id: 1,
    user_id: 1,
    rom_id: 1,
    created_at: "",
    updated_at: "",
    last_played: null,
    is_main_sibling: false,
    backlogged: false,
    now_playing: false,
    hidden: false,
    rating: 0,
    difficulty: 0,
    completion: 0,
    status: null,
    ...overrides,
  };
}

describe("applyLaunchStatus", () => {
  it("marks the game now playing", () => {
    const ru = makeRomUser({ now_playing: false });
    applyLaunchStatus(ru);
    expect(ru.now_playing).toBe(true);
  });

  it("fills an empty status with incomplete", () => {
    const ru = makeRomUser({ status: null });
    applyLaunchStatus(ru);
    expect(ru.status).toBe("incomplete");
  });

  it("rewinds a finished game to incomplete", () => {
    const ru = makeRomUser({ status: "finished" });
    applyLaunchStatus(ru);
    expect(ru.status).toBe("incomplete");
  });

  it("leaves an in-progress status untouched", () => {
    const ru = makeRomUser({ status: "incomplete" });
    applyLaunchStatus(ru);
    expect(ru.status).toBe("incomplete");
  });

  it.each(["completed_100", "retired", "never_playing"] as const)(
    "protects the %s status the user set on purpose",
    (status) => {
      const ru = makeRomUser({ status });
      applyLaunchStatus(ru);
      // now_playing is a separate orthogonal flag, so it still flips on,
      // but the deliberate enum status is preserved.
      expect(ru.now_playing).toBe(true);
      expect(ru.status).toBe(status);
    },
  );
});

function makeRom(romUser: RomUserSchema): SimpleRom {
  return { id: 1, rom_user: romUser } as unknown as SimpleRom;
}

describe("recordLaunch", () => {
  beforeEach(() => {
    updateUserRomProps.mockReset();
  });

  it("applies the launch status and persists it with last_played", () => {
    updateUserRomProps.mockResolvedValue({} as never);
    const ru = makeRomUser({ status: null });
    recordLaunch(makeRom(ru));

    expect(ru.now_playing).toBe(true);
    expect(ru.status).toBe("incomplete");
    expect(updateUserRomProps).toHaveBeenCalledWith({
      romId: 1,
      data: ru,
      updateLastPlayed: true,
    });
  });

  it("reverts the local mutation when the write fails", async () => {
    updateUserRomProps.mockRejectedValue(new Error("boom"));
    const ru = makeRomUser({ status: "finished", now_playing: false });
    recordLaunch(makeRom(ru));

    // Optimistic update is visible synchronously...
    expect(ru.now_playing).toBe(true);
    expect(ru.status).toBe("incomplete");

    // ...then reverted once the rejected write settles.
    await vi.waitFor(() => {
      expect(ru.now_playing).toBe(false);
      expect(ru.status).toBe("finished");
    });
  });
});
