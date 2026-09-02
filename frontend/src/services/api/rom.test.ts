import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/services/api";
import romApi, { type UpdateRom } from "@/services/api/rom";

vi.mock("@/services/api", () => ({
  default: { put: vi.fn().mockResolvedValue({ data: {} }) },
}));
vi.mock("@/services/socket", () => ({ default: { emit: vi.fn() } }));

const put = vi.mocked(api.put);

/** The FormData `updateRom` put on the wire. */
async function sentFields(rom: UpdateRom): Promise<FormData> {
  await romApi.updateRom({ rom });
  return put.mock.calls[0][1] as FormData;
}

function buildRom(overrides: Partial<UpdateRom> = {}): UpdateRom {
  return { id: 1, name: "Game", ...overrides } as UpdateRom;
}

beforeEach(() => {
  put.mockClear();
});

describe("updateRom", () => {
  // An id missing from the serializer is silently dropped: the endpoint
  // preserves the stored value for any field the form omits, so the save
  // reports success while the edit never lands.
  it.each([
    "igdb_id",
    "sgdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "flashpoint_id",
    "hasheous_id",
    "tgdb_id",
    "hltb_id",
    "steam_id",
    "libretro_id",
  ])("sends %s", async (field) => {
    const fields = await sentFields(buildRom({ [field]: 1234 }));

    expect(fields.get(field)).toBe("1234");
  });

  it.each([
    "igdb_metadata",
    "moby_metadata",
    "ss_metadata",
    "launchbox_metadata",
    "hasheous_metadata",
    "flashpoint_metadata",
    "hltb_metadata",
    "steam_metadata",
  ])("sends edited raw %s", async (field) => {
    const raw = JSON.stringify({ edited: true });

    const fields = await sentFields(
      buildRom({ raw_metadata: { [field]: raw } }),
    );

    expect(fields.get(`raw_${field}`)).toBe(raw);
  });
});
