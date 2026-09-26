import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { sessionStateName } from "@/services/api/state";

describe("sessionStateName", () => {
  const originalTZ = process.env.TZ;

  beforeEach(() => {
    process.env.TZ = "America/Sao_Paulo";
  });

  afterEach(() => {
    process.env.TZ = originalTZ;
  });

  it("stamps the name with the local time of the capture", () => {
    const capturedAt = new Date(Date.UTC(2026, 8, 22, 22, 10, 13, 849));

    expect(sessionStateName({ fs_name_no_ext: "suikoden " }, capturedAt)).toBe(
      "suikoden [2026-09-22 19-10-13-849]",
    );
  });

  it("zero-pads every component", () => {
    const capturedAt = new Date(Date.UTC(2026, 0, 2, 6, 4, 5, 7));

    expect(sessionStateName({ fs_name_no_ext: "game" }, capturedAt)).toBe(
      "game [2026-01-02 03-04-05-007]",
    );
  });
});
