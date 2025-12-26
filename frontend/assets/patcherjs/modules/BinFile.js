/*
 * BinFile.js (last update: 2024-08-21)
 * by Marc Robledo, https://www.marcrobledo.com
 *
 * a JS class for reading/writing sequentially binary data from/to a file
 * that allows much more manipulation than simple DataView
 * compatible with both browsers and Node.js
 *
 * MIT License
 *
 * Copyright (c) 2014-2024 Marc Robledo
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

function BinFile(source, onLoad) {
  this.littleEndian = false;
  this.offset = 0;
  this._lastRead = null;
  this._offsetsStack = [];

  if (
    BinFile.RUNTIME_ENVIROMENT === "browser" &&
    (source instanceof File ||
      source instanceof FileList ||
      (source instanceof HTMLElement &&
        source.tagName === "INPUT" &&
        source.type === "file"))
  ) {
    if (source instanceof HTMLElement) source = source.files;
    if (source instanceof FileList) source = source[0];

    this.fileName = source.name;
    this.fileType = source.type;
    this.fileSize = source.size;

    if (typeof window.FileReader !== "function")
      throw new Error("Incompatible browser");

    this._fileReader = new FileReader();
    this._fileReader.addEventListener(
      "load",
      function () {
        this.binFile._u8array = new Uint8Array(this.result);

        if (typeof onLoad === "function") onLoad(this.binFile);
      },
      false,
    );

    this._fileReader.binFile = this;

    this._fileReader.readAsArrayBuffer(source);
  } else if (
    BinFile.RUNTIME_ENVIROMENT === "node" &&
    typeof source === "string"
  ) {
    if (!nodeFs.existsSync(source)) throw new Error(source + " does not exist");

    const arrayBuffer = nodeFs.readFileSync(source);

    this.fileName = nodePath.basename(source);
    this.fileType = nodeFs.statSync(source).type;
    this.fileSize = arrayBuffer.byteLength;

    this._u8array = new Uint8Array(arrayBuffer);

    if (typeof onLoad === "function") onLoad(this);
  } else if (source instanceof BinFile) {
    /* if source is another BinFile, clone it */
    this.fileName = source.fileName;
    this.fileType = source.fileType;
    this.fileSize = source.fileSize;

    this._u8array = new Uint8Array(source._u8array.buffer.slice());

    if (typeof onLoad === "function") onLoad(this);
  } else if (source instanceof ArrayBuffer) {
    this.fileName = "file.bin";
    this.fileType = "application/octet-stream";
    this.fileSize = source.byteLength;

    this._u8array = new Uint8Array(source);

    if (typeof onLoad === "function") onLoad(this);
  } else if (ArrayBuffer.isView(source)) {
    /* source is TypedArray */
    this.fileName = "file.bin";
    this.fileType = "application/octet-stream";
    this.fileSize = source.buffer.byteLength;

    this._u8array = new Uint8Array(source.buffer);

    if (typeof onLoad === "function") onLoad(this);
  } else if (typeof source === "number") {
    /* source is integer, create new empty file */
    this.fileName = "file.bin";
    this.fileType = "application/octet-stream";
    this.fileSize = source;

    this._u8array = new Uint8Array(new ArrayBuffer(source));

    if (typeof onLoad === "function") onLoad(this);
  } else {
    throw new Error("invalid BinFile source");
  }
}
BinFile.RUNTIME_ENVIROMENT = (function () {
  if (typeof window === "object" && typeof window.document === "object")
    return "browser";
  else if (
    typeof WorkerGlobalScope === "function" &&
    self instanceof WorkerGlobalScope
  )
    return "webworker";
  else if (
    typeof require === "function" &&
    typeof process === "object" &&
    typeof process.versions === "object" &&
    typeof process.versions.node === "string"
  )
    return "node";
  else return null;
})();
BinFile.DEVICE_LITTLE_ENDIAN = (function () {
  /* https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/DataView#Endianness */
  var buffer = new ArrayBuffer(2);
  new DataView(buffer).setInt16(0, 256, true /* littleEndian */);
  // Int16Array uses the platform's endianness.
  return new Int16Array(buffer)[0] === 256;
})();

BinFile.prototype.push = function () {
  this._offsetsStack.push(this.offset);
};
BinFile.prototype.pop = function () {
  this.seek(this._offsetsStack.pop());
};
BinFile.prototype.seek = function (offset) {
  this.offset = offset;
};
BinFile.prototype.skip = function (nBytes) {
  this.offset += nBytes;
};
BinFile.prototype.isEOF = function () {
  return !(this.offset < this.fileSize);
};
BinFile.prototype.slice = function (offset, len, doNotClone) {
  if (typeof offset !== "number" || offset < 0) offset = 0;
  else if (offset >= this.fileSize) throw new Error("out of bounds slicing");
  else offset = Math.floor(offset);

  if (
    typeof len !== "number" ||
    offset < 0 ||
    offset + len >= this.fileSize.length
  )
    len = this.fileSize - offset;
  else if (len === 0) throw new Error("zero length provided for slicing");
  else len = Math.floor(len);

  if (offset === 0 && len === this.fileSize && doNotClone) return this;

  var newFile = new BinFile(this._u8array.buffer.slice(offset, offset + len));
  newFile.fileName = this.fileName;
  newFile.fileType = this.fileType;
  newFile.littleEndian = this.littleEndian;
  return newFile;
};
BinFile.prototype.prependBytes = function (bytes) {
  var newFile = new BinFile(this.fileSize + bytes.length);
  newFile.seek(0);
  newFile.writeBytes(bytes);
  this.copyTo(newFile, 0, this.fileSize, bytes.length);

  this.fileSize = newFile.fileSize;
  this._u8array = newFile._u8array;
  return this;
};
BinFile.prototype.removeLeadingBytes = function (nBytes) {
  this.seek(0);
  var oldData = this.readBytes(nBytes);
  var newFile = this.slice(nBytes.length);

  this.fileSize = newFile.fileSize;
  this._u8array = newFile._u8array;
  return oldData;
};

BinFile.prototype.copyTo = function (target, offsetSource, len, offsetTarget) {
  if (!(target instanceof BinFile))
    throw new Error("target is not a BinFile object");

  if (typeof offsetTarget !== "number") offsetTarget = offsetSource;

  len = len || this.fileSize - offsetSource;

  for (var i = 0; i < len; i++) {
    target._u8array[offsetTarget + i] = this._u8array[offsetSource + i];
  }
};

BinFile.prototype.save = function () {
  if (BinFile.RUNTIME_ENVIROMENT === "browser") {
    var fileBlob = new Blob([this._u8array], { type: this.fileType });
    var blobUrl = URL.createObjectURL(fileBlob);
    var a = document.createElement("a");
    a.href = blobUrl;
    a.download = this.fileName;
    document.body.appendChild(a);
    a.dispatchEvent(new MouseEvent("click"));
    URL.revokeObjectURL(blobUrl);
    document.body.removeChild(a);
  } else if (BinFile.RUNTIME_ENVIROMENT === "node") {
    nodeFs.writeFileSync(this.fileName, Buffer.from(this._u8array.buffer));
  } else {
    throw new Error("invalid runtime environment, can't save file");
  }
};

BinFile.prototype.getExtension = function () {
  var ext = this.fileName ? this.fileName.toLowerCase().match(/\.(\w+)$/) : "";

  return ext ? ext[1] : "";
};
BinFile.prototype.getName = function () {
  return this.fileName.replace(
    new RegExp("\\." + this.getExtension() + "$", "i"),
    "",
  );
};
BinFile.prototype.setExtension = function (newExtension) {
  return (this.fileName = this.getName() + "." + newExtension);
};
BinFile.prototype.setName = function (newName) {
  return (this.fileName = newName + "." + this.getExtension());
};

BinFile.prototype.readU8 = function () {
  this._lastRead = this._u8array[this.offset++];

  return this._lastRead;
};
BinFile.prototype.readU16 = function () {
  if (this.littleEndian)
    this._lastRead =
      this._u8array[this.offset] + (this._u8array[this.offset + 1] << 8);
  else
    this._lastRead =
      (this._u8array[this.offset] << 8) + this._u8array[this.offset + 1];

  this.offset += 2;
  return this._lastRead >>> 0;
};
BinFile.prototype.readU24 = function () {
  if (this.littleEndian)
    this._lastRead =
      this._u8array[this.offset] +
      (this._u8array[this.offset + 1] << 8) +
      (this._u8array[this.offset + 2] << 16);
  else
    this._lastRead =
      (this._u8array[this.offset] << 16) +
      (this._u8array[this.offset + 1] << 8) +
      this._u8array[this.offset + 2];

  this.offset += 3;
  return this._lastRead >>> 0;
};
BinFile.prototype.readU32 = function () {
  if (this.littleEndian)
    this._lastRead =
      this._u8array[this.offset] +
      (this._u8array[this.offset + 1] << 8) +
      (this._u8array[this.offset + 2] << 16) +
      (this._u8array[this.offset + 3] << 24);
  else
    this._lastRead =
      (this._u8array[this.offset] << 24) +
      (this._u8array[this.offset + 1] << 16) +
      (this._u8array[this.offset + 2] << 8) +
      this._u8array[this.offset + 3];

  this.offset += 4;
  return this._lastRead >>> 0;
};
BinFile.prototype.readU64 = function () {
  if (this.littleEndian)
    this._lastRead =
      this._u8array[this.offset] +
      (this._u8array[this.offset + 1] << 8) +
      (this._u8array[this.offset + 2] << 16) +
      (this._u8array[this.offset + 3] << 24) +
      (this._u8array[this.offset + 4] << 32) +
      (this._u8array[this.offset + 5] << 40) +
      (this._u8array[this.offset + 6] << 48) +
      (this._u8array[this.offset + 7] << 56);
  else
    this._lastRead =
      (this._u8array[this.offset] << 56) +
      (this._u8array[this.offset + 1] << 48) +
      (this._u8array[this.offset + 2] << 40) +
      (this._u8array[this.offset + 3] << 32) +
      (this._u8array[this.offset + 4] << 24) +
      (this._u8array[this.offset + 5] << 16) +
      (this._u8array[this.offset + 6] << 8) +
      this._u8array[this.offset + 7];
  this.offset += 8;
  return this._lastRead >>> 0;
};

BinFile.prototype.readBytes = function (len) {
  this._lastRead = new Array(len);
  for (var i = 0; i < len; i++) {
    this._lastRead[i] = this._u8array[this.offset + i];
  }

  this.offset += len;
  return this._lastRead;
};

BinFile.prototype.readString = function (len) {
  this._lastRead = "";
  for (
    var i = 0;
    i < len &&
    this.offset + i < this.fileSize &&
    this._u8array[this.offset + i] > 0;
    i++
  )
    this._lastRead =
      this._lastRead + String.fromCharCode(this._u8array[this.offset + i]);

  this.offset += len;
  return this._lastRead;
};

BinFile.prototype.writeU8 = function (u8) {
  this._u8array[this.offset++] = u8;
};
BinFile.prototype.writeU16 = function (u16) {
  if (this.littleEndian) {
    this._u8array[this.offset] = u16 & 0xff;
    this._u8array[this.offset + 1] = u16 >> 8;
  } else {
    this._u8array[this.offset] = u16 >> 8;
    this._u8array[this.offset + 1] = u16 & 0xff;
  }

  this.offset += 2;
};
BinFile.prototype.writeU24 = function (u24) {
  if (this.littleEndian) {
    this._u8array[this.offset] = u24 & 0x0000ff;
    this._u8array[this.offset + 1] = (u24 & 0x00ff00) >> 8;
    this._u8array[this.offset + 2] = (u24 & 0xff0000) >> 16;
  } else {
    this._u8array[this.offset] = (u24 & 0xff0000) >> 16;
    this._u8array[this.offset + 1] = (u24 & 0x00ff00) >> 8;
    this._u8array[this.offset + 2] = u24 & 0x0000ff;
  }

  this.offset += 3;
};
BinFile.prototype.writeU32 = function (u32) {
  if (this.littleEndian) {
    this._u8array[this.offset] = u32 & 0x000000ff;
    this._u8array[this.offset + 1] = (u32 & 0x0000ff00) >> 8;
    this._u8array[this.offset + 2] = (u32 & 0x00ff0000) >> 16;
    this._u8array[this.offset + 3] = (u32 & 0xff000000) >> 24;
  } else {
    this._u8array[this.offset] = (u32 & 0xff000000) >> 24;
    this._u8array[this.offset + 1] = (u32 & 0x00ff0000) >> 16;
    this._u8array[this.offset + 2] = (u32 & 0x0000ff00) >> 8;
    this._u8array[this.offset + 3] = u32 & 0x000000ff;
  }

  this.offset += 4;
};

BinFile.prototype.writeBytes = function (a) {
  for (var i = 0; i < a.length; i++) this._u8array[this.offset + i] = a[i];

  this.offset += a.length;
};

BinFile.prototype.writeString = function (str, len) {
  len = len || str.length;
  for (var i = 0; i < str.length && i < len; i++)
    this._u8array[this.offset + i] = str.charCodeAt(i);

  for (; i < len; i++) this._u8array[this.offset + i] = 0x00;

  this.offset += len;
};

BinFile.prototype.swapBytes = function (swapSize, newFile) {
  if (typeof swapSize !== "number") {
    swapSize = 4;
  }

  if (this.fileSize % swapSize !== 0) {
    throw new Error("file size is not divisible by " + swapSize);
  }

  var swappedFile = new BinFile(this.fileSize);
  this.seek(0);
  while (!this.isEOF()) {
    swappedFile.writeBytes(this.readBytes(swapSize).reverse());
  }

  if (newFile) {
    swappedFile.fileName = this.fileName;
    swappedFile.fileType = this.fileType;

    return swappedFile;
  } else {
    this._u8array = swappedFile._u8array;

    return this;
  }
};

BinFile.prototype.hashSHA1 = async function (start, len) {
  if (
    typeof HashCalculator !== "object" ||
    typeof HashCalculator.sha1 !== "function"
  )
    throw new Error("no Hash object found or missing sha1 function");

  return HashCalculator.sha1(this.slice(start, len, true)._u8array.buffer);
};
BinFile.prototype.hashMD5 = function (start, len) {
  if (
    typeof HashCalculator !== "object" ||
    typeof HashCalculator.md5 !== "function"
  )
    throw new Error("no Hash object found or missing md5 function");

  return HashCalculator.md5(this.slice(start, len, true)._u8array.buffer);
};
BinFile.prototype.hashCRC32 = function (start, len) {
  if (
    typeof HashCalculator !== "object" ||
    typeof HashCalculator.crc32 !== "function"
  )
    throw new Error("no Hash object found or missing crc32 function");

  return HashCalculator.crc32(this.slice(start, len, true)._u8array.buffer);
};
BinFile.prototype.hashAdler32 = function (start, len) {
  if (
    typeof HashCalculator !== "object" ||
    typeof HashCalculator.adler32 !== "function"
  )
    throw new Error("no Hash object found or missing adler32 function");

  return HashCalculator.adler32(this.slice(start, len, true)._u8array.buffer);
};
BinFile.prototype.hashCRC16 = function (start, len) {
  if (
    typeof HashCalculator !== "object" ||
    typeof HashCalculator.crc16 !== "function"
  )
    throw new Error("no Hash object found or missing crc16 function");

  return HashCalculator.crc16(this.slice(start, len, true)._u8array.buffer);
};

if (
  BinFile.RUNTIME_ENVIROMENT === "node" &&
  typeof module !== "undefined" &&
  module.exports
) {
  module.exports = BinFile;
  HashCalculator = require("./HashCalculator");
  nodePath = require("path");
  nodeFs = require("fs");
}
