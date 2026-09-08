import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { DetailedRom } from "@/stores/roms";
import MetadataTab from "./MetadataTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const CRC = "aabbccdd";
const MD5 = "0123456789abcdef0123456789abcdef";
const SHA1 = "0123456789abcdef0123456789abcdef01234567";
const CHD_SHA1 = "89abcdef0123456789abcdef0123456789abcdef";
const RA = "fedcba9876543210fedcba9876543210";

function rom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 1,
    fs_name: "game.chd",
    fs_size_bytes: 1024,
    crc_hash: CRC,
    md5_hash: MD5,
    sha1_hash: SHA1,
    ra_hash: RA,
    has_simple_single_file: true,
    files: [{ chd_sha1_hash: "" }],
    ...overrides,
  } as DetailedRom;
}

function hashLabels(r: DetailedRom) {
  const wrapper = shallowMount(MetadataTab, { props: { rom: r } });
  return wrapper
    .findAllComponents({ name: "HashChip" })
    .map((c) => c.props("label"));
}

describe("MetadataTab hash rows", () => {
  // The files list and the firmware list both read SHA-1, CHD SHA-1, MD5,
  // CRC, RA. This tab used to lead with CRC, so the two tabs disagreed.
  it("orders hashes the same way every other surface does", () => {
    expect(hashLabels(rom())).toEqual(["SHA-1", "MD5", "CRC", "RA"]);
  });

  // Not reachable in the browser: the mock library holds no CHD.
  it("slots CHD SHA-1 directly after SHA-1 when the ROM is a CHD", () => {
    const chd = rom({
      files: [{ chd_sha1_hash: CHD_SHA1 }],
    } as Partial<DetailedRom>);

    expect(hashLabels(chd)).toEqual(["SHA-1", "CHD SHA-1", "MD5", "CRC", "RA"]);
  });
});
