// A minimal zip reader and writer on node:zlib, so the module needs no dependencies.
// Packs are untrusted: every limit is checked from the central directory before anything is inflated.
import { closeSync, fstatSync, openSync, readSync, writeFileSync } from "node:fs";
import { deflateRawSync, inflateRawSync } from "node:zlib";

const MB = 1024 * 1024;
const envNumber = (name, fallback) => {
  const n = Number(process.env[name]);
  return Number.isFinite(n) && n > 0 ? n : fallback;
};

export const MAX_ENTRIES = envNumber("THEMEABLE_ZIP_MAX_ENTRIES", 2000);
export const MAX_TOTAL_BYTES = envNumber("THEMEABLE_ZIP_MAX_TOTAL_MB", 64) * MB;
export const MAX_FILE_BYTES = envNumber("THEMEABLE_ZIP_MAX_FILE_MB", 16) * MB;
export const MAX_RATIO = envNumber("THEMEABLE_ZIP_MAX_RATIO", 100);
export const LIMITS = Object.freeze({ entries: MAX_ENTRIES, total: MAX_TOTAL_BYTES, file: MAX_FILE_BYTES, ratio: MAX_RATIO });

const EOCD = 0x06054b50;
const CENTRAL = 0x02014b50;
const LOCAL = 0x04034b50;
const STORED = 0;
const DEFLATED = 8;
const S_IFMT = 0o170000;
const S_IFLNK = 0o120000;

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

export function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const mb = (bytes) => `${Math.round((bytes / MB) * 10) / 10} MB`;

/** Why an entry name is unsafe, or null; names must stay relative and inside the archive. */
export function unsafeName(name) {
  if (!name || name.includes("\0")) return "an empty or binary name";
  if (name.includes("\\")) return "a backslash in the path";
  if (name.startsWith("/") || /^[A-Za-z]:/.test(name)) return "an absolute path";
  if (name.split("/").some((part) => part === "..")) return 'a ".." path that leaves the archive';
  return null;
}

/**
 * Opens a zip and checks its central directory against the limits.
 * Returns { names, size(name), read(name), close() }; read() inflates one file and checks its CRC.
 */
export function openZip(file, limits = LIMITS) {
  const fd = openSync(file, "r");
  try {
    return parse(fd, limits);
  } catch (e) {
    closeSync(fd);
    throw e;
  }
}

function readAt(fd, position, length, fileSize) {
  if (position < 0 || position + length > fileSize) throw new Error("the archive is truncated or damaged");
  const buf = Buffer.alloc(length);
  readSync(fd, buf, 0, length, position);
  return buf;
}

function parse(fd, limits) {
  const fileSize = fstatSync(fd).size;
  if (fileSize < 22) throw new Error("not a zip archive (the file is too small)");
  const tailLength = Math.min(fileSize, 22 + 0xffff);
  const tail = readAt(fd, fileSize - tailLength, tailLength, fileSize);
  let eocd = -1;
  for (let i = tail.length - 22; i >= 0; i--) {
    if (tail.readUInt32LE(i) === EOCD) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("not a zip archive (no end of central directory)");
  const disk = tail.readUInt16LE(eocd + 4);
  const cdDisk = tail.readUInt16LE(eocd + 6);
  const diskEntries = tail.readUInt16LE(eocd + 8);
  const count = tail.readUInt16LE(eocd + 10);
  const cdSize = tail.readUInt32LE(eocd + 12);
  const cdOffset = tail.readUInt32LE(eocd + 16);
  if (disk !== 0 || cdDisk !== 0 || diskEntries !== count) throw new Error("multi-disk (split) archives are not supported");
  if (count === 0xffff || cdSize === 0xffffffff || cdOffset === 0xffffffff) {
    throw new Error("ZIP64 archives are not supported");
  }
  if (count > limits.entries) throw new Error(`the archive has ${count} entries; the limit is ${limits.entries}`);

  const cd = readAt(fd, cdOffset, cdSize, fileSize);
  const entries = new Map();
  let total = 0;
  let compressed = 0;
  let p = 0;
  for (let i = 0; i < count; i++) {
    if (p + 46 > cd.length || cd.readUInt32LE(p) !== CENTRAL) throw new Error("the archive's central directory is damaged");
    const flags = cd.readUInt16LE(p + 8);
    const method = cd.readUInt16LE(p + 10);
    const crc = cd.readUInt32LE(p + 16);
    const compSize = cd.readUInt32LE(p + 20);
    const size = cd.readUInt32LE(p + 24);
    const nameLength = cd.readUInt16LE(p + 28);
    const extraLength = cd.readUInt16LE(p + 30);
    const commentLength = cd.readUInt16LE(p + 32);
    const entryDisk = cd.readUInt16LE(p + 34);
    const mode = cd.readUInt32LE(p + 38) >>> 16;
    const offset = cd.readUInt32LE(p + 42);
    if (p + 46 + nameLength > cd.length) throw new Error("the archive's central directory is damaged");
    const raw = cd.subarray(p + 46, p + 46 + nameLength);
    const name = flags & 0x800 ? raw.toString("utf8") : raw.toString("latin1");
    p += 46 + nameLength + extraLength + commentLength;

    const unsafe = unsafeName(name);
    if (unsafe) throw new Error(`"${name}" has ${unsafe}`);
    if (entryDisk !== 0) throw new Error("multi-disk (split) archives are not supported");
    if (flags & 0x1) throw new Error(`"${name}" is encrypted; encrypted archives are not supported`);
    if (compSize === 0xffffffff || size === 0xffffffff || offset === 0xffffffff) throw new Error("ZIP64 archives are not supported");
    if (name.endsWith("/")) continue;
    if ((mode & S_IFMT) === S_IFLNK) throw new Error(`"${name}" is a symbolic link; links are not allowed`);
    if (method !== STORED && method !== DEFLATED) {
      throw new Error(`"${name}" uses compression method ${method}; only stored and deflated files are supported`);
    }
    if (entries.has(name)) throw new Error(`"${name}" appears more than once`);
    if (size > limits.file) throw new Error(`"${name}" is ${mb(size)} uncompressed; the limit is ${mb(limits.file)} per file`);
    total += size;
    compressed += compSize;
    if (total > limits.total) throw new Error(`the archive holds more than ${mb(limits.total)} uncompressed; that is the limit`);
    entries.set(name, { method, crc, compSize, size, offset });
  }
  if (total > 0 && total / Math.max(compressed, 1) > limits.ratio) {
    throw new Error(`the archive compresses more than ${limits.ratio}:1, which is not allowed`);
  }

  return {
    names: [...entries.keys()],
    size: (name) => entries.get(name)?.size,
    read(name) {
      const e = entries.get(name);
      if (!e) throw new Error(`"${name}" is not in the archive`);
      const header = readAt(fd, e.offset, 30, fileSize);
      if (header.readUInt32LE(0) !== LOCAL) throw new Error(`"${name}": the archive is damaged`);
      const start = e.offset + 30 + header.readUInt16LE(26) + header.readUInt16LE(28);
      const data = readAt(fd, start, e.compSize, fileSize);
      let out;
      try {
        out = e.method === STORED ? data : inflateRawSync(data, { maxOutputLength: Math.max(e.size, 1) });
      } catch (err) {
        throw new Error(`"${name}" could not be decompressed (${err.code ?? err.message})`);
      }
      if (out.length !== e.size || crc32(out) !== e.crc) throw new Error(`"${name}" is damaged (size or checksum mismatch)`);
      return out;
    },
    close: () => closeSync(fd),
  };
}

/** Writes files ([{ name, data }]) to a deflated zip with UTF-8 names. */
export function writeZip(file, files) {
  const locals = [];
  const centrals = [];
  let offset = 0;
  // 1980-01-01 00:00, so the same files always make the same archive.
  const dosTime = 0;
  const dosDate = (0 << 9) | (1 << 5) | 1;
  for (const { name, data } of files) {
    const unsafe = unsafeName(name);
    if (unsafe) throw new Error(`"${name}" has ${unsafe}`);
    const nameBuf = Buffer.from(name, "utf8");
    const deflated = deflateRawSync(data);
    const stored = deflated.length >= data.length;
    const body = stored ? data : deflated;
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(LOCAL, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x800, 6);
    local.writeUInt16LE(stored ? STORED : DEFLATED, 8);
    local.writeUInt16LE(dosTime, 10);
    local.writeUInt16LE(dosDate, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(body.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(CENTRAL, 0);
    central.writeUInt16LE((3 << 8) | 20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x800, 8);
    central.writeUInt16LE(stored ? STORED : DEFLATED, 10);
    central.writeUInt16LE(dosTime, 12);
    central.writeUInt16LE(dosDate, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(body.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt32LE((0o100644 << 16) >>> 0, 38);
    central.writeUInt32LE(offset, 42);
    locals.push(local, nameBuf, body);
    centrals.push(central, nameBuf);
    offset += 30 + nameBuf.length + body.length;
  }
  const cd = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(EOCD, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(cd.length, 12);
  end.writeUInt32LE(offset, 16);
  writeFileSync(file, Buffer.concat([...locals, cd, end]));
}
