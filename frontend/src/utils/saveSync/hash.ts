import { unzipSync } from "fflate";
import SparkMD5 from "spark-md5";

const EOCD_SIGNATURE = [0x50, 0x4b, 0x05, 0x06];
// The end-of-central-directory record sits within its own size plus the
// longest possible archive comment of the end, which is where Python looks.
const EOCD_SEARCH_BYTES = 22 + 0xffff;

function md5(bytes: Uint8Array): string {
  const whole =
    bytes.byteOffset === 0 && bytes.byteLength === bytes.buffer.byteLength;
  const hash = new SparkMD5.ArrayBuffer();
  hash.append((whole ? bytes.buffer : bytes.slice().buffer) as ArrayBuffer);
  return hash.end();
}

function looksLikeZip(bytes: Uint8Array): boolean {
  const start = Math.max(0, bytes.length - EOCD_SEARCH_BYTES);
  for (let i = bytes.length - 4; i >= start; i--) {
    if (EOCD_SIGNATURE.every((byte, offset) => bytes[i + offset] === byte))
      return true;
  }
  return false;
}

/** The hash the server stores for a save, so identical files negotiate as such. */
export function saveContentHash(bytes: Uint8Array): string {
  // A zip hashes by its entries, as `hash_zip_contents` does.
  if (looksLikeZip(bytes)) {
    try {
      const entries = unzipSync(bytes);
      const lines = Object.keys(entries)
        .filter((name) => !name.endsWith("/"))
        .sort()
        .map((name) => `${name}:${md5(entries[name]!)}`);
      return SparkMD5.hash(lines.join("\n"));
    } catch {
      // Not a readable archive after all.
    }
  }
  return md5(bytes);
}

/** Byte equality, cheaper than hashing both sides. */
export function bytesEqual(
  a: Uint8Array | null,
  b: Uint8Array | null,
): boolean {
  if (!a || !b) return a === b;
  if (a.byteLength !== b.byteLength) return false;
  for (let i = 0; i < a.byteLength; i++) if (a[i] !== b[i]) return false;
  return true;
}
