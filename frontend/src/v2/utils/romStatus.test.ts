import { describe, expect, it } from "vitest";
import type { RomUserSchema } from "@/__generated__";
import { applyLaunchStatus } from "./romStatus";

// Minimal RomUserSchema factory — only the fields applyLaunchStatus reads
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
