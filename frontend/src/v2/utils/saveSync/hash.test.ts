import { describe, expect, it } from "vitest";
import { saveContentHash } from "./hash";

// Built and hashed by the backend's `hash_zip_contents`, so the two must agree.
const ZIP_BASE64 =
  "UEsDBBQAAAAIAAeGQ11gCE0wDQAAAFAAAAAKAAAAQy9TQVZFLkRBVCsoyk8vSi0uLqASDQBQSwMEFAAAAAgAB4ZDXQAAAAACAAAAAAAAAAIAAABDLwMAUEsDBBQAAAAIAAeGQ102gjueCAAAAAYAAAAFAAAAQS5UWFTLOLwyJycfAFBLAQIUAxQAAAAIAAeGQ11gCE0wDQAAAFAAAAAKAAAAAAAAAAAAAACAAQAAAABDL1NBVkUuREFUUEsBAhQDFAAAAAgAB4ZDXQAAAAACAAAAAAAAAAIAAAAAAAAAAAAQAP1BNQAAAEMvUEsBAhQDFAAAAAgAB4ZDXTaCO54IAAAABgAAAAUAAAAAAAAAAAAAAIABVwAAAEEuVFhUUEsFBgAAAAADAAMAmwAAAIIAAAAAAA==";

function fromBase64(value: string): Uint8Array {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
}

describe("saveContentHash", () => {
  it("hashes a plain file as its md5", () => {
    expect(saveContentHash(new Uint8Array([83, 82, 65, 77, 0, 1, 2]))).toBe(
      "655aa3ec09bb48b00face19877d6d50a",
    );
  });

  it("hashes a zip by its entries, as the server does", () => {
    expect(saveContentHash(fromBase64(ZIP_BASE64))).toBe(
      "c11dca62d5479918ad24ea47cd8370b6",
    );
  });

  it("falls back to the md5 of a file that only resembles a zip", () => {
    const bytes = new Uint8Array([1, 2, 0x50, 0x4b, 0x05, 0x06, 3]);
    expect(saveContentHash(bytes)).toMatch(/^[0-9a-f]{32}$/);
  });
});
