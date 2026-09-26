import { beforeAll, describe, expect, it } from "vitest";
import type { AuditEventSchema } from "@/__generated__";
import { loadLocale } from "@/locales";
import { ROUTES } from "@/plugins/routeNames";
import { describeAuditEvent } from "@/v2/utils/auditEvents";
import { makeAuditEvent } from "@/v2/utils/auditEvents.fixtures";

function event(
  action: string,
  overrides: Partial<AuditEventSchema> = {},
): AuditEventSchema {
  return makeAuditEvent({ action, ...overrides });
}

beforeAll(async () => {
  await loadLocale("en_US");
});

describe("describeAuditEvent", () => {
  it("names a downloaded game and links to it", () => {
    const view = describeAuditEvent(
      event("rom.download", {
        data: { file_name: "Metroid (USA).nes", size_bytes: 2048 },
      }),
    );

    expect(view.title).toBe("Downloaded Metroid");
    expect(view.detail).toMatch(/^Metroid \(USA\)\.nes · 2(\.0+)? KB$/);
    expect(view.to).toEqual({ name: ROUTES.ROM, params: { rom: "12" } });
  });

  it("gives how long a game was played", () => {
    const short = describeAuditEvent(
      event("rom.play", { data: { duration_ms: 45 * 60 * 1000 } }),
    );
    const long = describeAuditEvent(
      event("rom.play", { data: { duration_ms: 150 * 60 * 1000 } }),
    );

    expect(short.title).toBe("Played Metroid");
    expect(short.detail).toBe("45m");
    expect(long.detail).toBe("2.5h");
  });

  it("lists what an edit changed and the rename", () => {
    const view = describeAuditEvent(
      event("rom.edit", {
        data: {
          changed: ["name", "fs_name"],
          name: { from: "metroid", to: "Metroid" },
        },
      }),
    );

    expect(view.detail).toBe("Changed: name and file name · metroid → Metroid");
  });

  it("names the providers of a manual match", () => {
    const view = describeAuditEvent(
      event("rom.match", { data: { providers: { igdb_id: 1, sgdb_id: 2 } } }),
    );

    expect(view.title).toBe("Matched Metroid");
    expect(view.detail).toBe("IGDB and SGDB");
  });

  it("doesn't link to what was deleted", () => {
    const view = describeAuditEvent(
      event("rom.delete", { data: { deleted_from_fs: true } }),
    );

    expect(view.detail).toBe("Also deleted from disk");
    expect(view.to).toBeNull();
  });

  it("counts the games a bulk download took from a platform", () => {
    const view = describeAuditEvent(
      event("rom.bulk_download", {
        target_type: "platform",
        target_id: "3",
        target_name: "NES",
        data: { count: 4 },
      }),
    );

    expect(view.title).toBe("Downloaded 4 games from NES");
    expect(view.to).toEqual({
      name: ROUTES.PLATFORM,
      params: { platform: "3" },
    });
  });

  it("reports how a scan ended", () => {
    expect(
      describeAuditEvent(
        event("scan.finish", { data: { status: "completed", new_roms: 1 } }),
      ).detail,
    ).toBe("1 new game");
    expect(
      describeAuditEvent(
        event("scan.finish", { data: { status: "failed", error: "boom" } }),
      ),
    ).toMatchObject({ title: "A scan failed", detail: "boom" });
  });

  it("shows a role change in words", () => {
    const view = describeAuditEvent(
      event("user.edit", {
        target_type: "user",
        target_name: "kid",
        data: { changed: ["role"], role: { from: "user", to: "admin" } },
      }),
    );

    expect(view.title).toBe("Edited the user kid");
    expect(view.detail).toContain("Role:");
  });

  it("falls back to an id when the target has no name", () => {
    const view = describeAuditEvent(event("rom.create", { target_name: null }));

    expect(view.title).toBe("Added #12");
  });

  it("colors a failure apart from its category", () => {
    expect(
      describeAuditEvent(event("rom.play", { category: "consumption" })).tone,
    ).toBe("var(--r-color-brand-primary)");
    expect(
      describeAuditEvent(
        event("auth.login_failed", { category: "security", data: {} }),
      ).tone,
    ).toBe("var(--r-color-danger)");
  });

  it("names a failed sign-in only by an account's own name", () => {
    expect(
      describeAuditEvent(
        event("auth.login_failed", { data: { username: "maria" } }),
      ).title,
    ).toBe("Failed to sign in as maria");
    expect(
      describeAuditEvent(
        event("auth.login_failed", { data: { username: null } }),
      ).title,
    ).toBe("Failed to sign in with an unknown username");
  });

  it("tells a player's load from a download", () => {
    expect(describeAuditEvent(event("rom.player_load")).title).toBe(
      "Loaded Metroid into a player",
    );
  });

  it("shows an action it doesn't know as it came", () => {
    const view = describeAuditEvent(event("rom.teleport"));

    expect(view.title).toBe("rom.teleport Metroid");
    expect(view.to).toBeNull();
  });
});
