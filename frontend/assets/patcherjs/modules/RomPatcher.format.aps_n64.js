/* APS (N64) module for Rom Patcher JS v20180930 - Marc Robledo 2017-2018 - http://www.marcrobledo.com/license */
/* File format specification: https://github.com/btimofeev/UniPatcher/wiki/APS-(N64) */

const APS_N64_MAGIC = "APS10";
const APS_RECORD_RLE = 0x0000;
const APS_RECORD_SIMPLE = 0x01;
const APS_N64_MODE = 0x01;
if (typeof module !== "undefined" && module.exports) {
  module.exports = APS;
}
function APS() {
  this.records = [];
  this.headerType = 0;
  this.encodingMethod = 0;
  this.description = "no description";

  this.header = {};
}
APS.prototype.addRecord = function (o, d) {
  this.records.push({ offset: o, type: APS_RECORD_SIMPLE, data: d });
};
APS.prototype.addRLERecord = function (o, b, l) {
  this.records.push({ offset: o, type: APS_RECORD_RLE, length: l, byte: b });
};
APS.prototype.toString = function () {
  var s = "Total records: " + this.records.length;
  s += "\nHeader type: " + this.headerType;
  if (this.headerType === APS_N64_MODE) {
    s += " (N64)";
  }
  s += "\nEncoding method: " + this.encodingMethod;
  s += "\nDescription: " + this.description;
  s += "\nHeader: " + JSON.stringify(this.header);
  return s;
};
APS.prototype.validateSource = function (sourceFile) {
  if (this.headerType === APS_N64_MODE) {
    sourceFile.seek(0x3c);
    if (sourceFile.readString(3) !== this.header.cartId) return false;

    sourceFile.seek(0x10);
    var crc = sourceFile.readBytes(8);
    for (var i = 0; i < 8; i++) {
      if (crc[i] !== this.header.crc[i]) return false;
    }
  }
  return true;
};
APS.prototype.getValidationInfo = function () {
  if (this.headerType === APS_N64_MODE) {
    return (
      this.header.cartId +
      " (" +
      this.header.crc.reduce(function (hex, b) {
        if (b < 16) return hex + "0" + b.toString(16);
        else return hex + b.toString(16);
      }, "") +
      ")"
    );
  }
  return null;
};
APS.prototype.export = function (fileName) {
  var patchFileSize = 61;
  if (this.headerType === APS_N64_MODE) patchFileSize += 17;

  for (var i = 0; i < this.records.length; i++) {
    if (this.records[i].type === APS_RECORD_RLE) patchFileSize += 7;
    else patchFileSize += 5 + this.records[i].data.length; //offset+length+data
  }

  tempFile = new BinFile(patchFileSize);
  tempFile.littleEndian = true;
  tempFile.fileName = fileName + ".aps";
  tempFile.writeString(APS_N64_MAGIC, APS_N64_MAGIC.length);
  tempFile.writeU8(this.headerType);
  tempFile.writeU8(this.encodingMethod);
  tempFile.writeString(this.description, 50);

  if (this.headerType === APS_N64_MODE) {
    tempFile.writeU8(this.header.originalN64Format);
    tempFile.writeString(this.header.cartId, 3);
    tempFile.writeBytes(this.header.crc);
    tempFile.writeBytes(this.header.pad);
  }
  tempFile.writeU32(this.header.sizeOutput);

  for (var i = 0; i < this.records.length; i++) {
    var rec = this.records[i];
    tempFile.writeU32(rec.offset);
    if (rec.type === APS_RECORD_RLE) {
      tempFile.writeU8(0x00);
      tempFile.writeU8(rec.byte);
      tempFile.writeU8(rec.length);
    } else {
      tempFile.writeU8(rec.data.length);
      tempFile.writeBytes(rec.data);
    }
  }

  return tempFile;
};

APS.prototype.apply = function (romFile, validate) {
  if (validate && !this.validateSource(romFile)) {
    throw new Error("Source ROM checksum mismatch");
  }

  tempFile = new BinFile(this.header.sizeOutput);
  romFile.copyTo(tempFile, 0, tempFile.fileSize);

  for (var i = 0; i < this.records.length; i++) {
    tempFile.seek(this.records[i].offset);
    if (this.records[i].type === APS_RECORD_RLE) {
      for (var j = 0; j < this.records[i].length; j++)
        tempFile.writeU8(this.records[i].byte);
    } else {
      tempFile.writeBytes(this.records[i].data);
    }
  }

  return tempFile;
};

APS.MAGIC = APS_N64_MAGIC;

APS.fromFile = function (patchFile) {
  var patch = new APS();
  patchFile.littleEndian = true;

  patchFile.seek(5);
  patch.headerType = patchFile.readU8();
  patch.encodingMethod = patchFile.readU8();
  patch.description = patchFile.readString(50);

  var seek;
  if (patch.headerType === APS_N64_MODE) {
    patch.header.originalN64Format = patchFile.readU8();
    patch.header.cartId = patchFile.readString(3);
    patch.header.crc = patchFile.readBytes(8);
    patch.header.pad = patchFile.readBytes(5);
  }
  patch.header.sizeOutput = patchFile.readU32();

  while (!patchFile.isEOF()) {
    var offset = patchFile.readU32();
    var length = patchFile.readU8();

    if (length === APS_RECORD_RLE)
      patch.addRLERecord(
        offset,
        patchFile.readU8(seek),
        patchFile.readU8(seek + 1),
      );
    else patch.addRecord(offset, patchFile.readBytes(length));
  }
  return patch;
};

APS.buildFromRoms = function (original, modified) {
  var patch = new APS();

  if (original.readU32() === 0x80371240) {
    //is N64 ROM
    patch.headerType = APS_N64_MODE;

    patch.header.originalN64Format = /\.v64$/i.test(original.fileName) ? 0 : 1;
    original.seek(0x3c);
    patch.header.cartId = original.readString(3);
    original.seek(0x10);
    patch.header.crc = original.readBytes(8);
    patch.header.pad = [0, 0, 0, 0, 0];
  }
  patch.header.sizeOutput = modified.fileSize;

  original.seek(0);
  modified.seek(0);

  while (!modified.isEOF()) {
    var b1 = original.isEOF() ? 0x00 : original.readU8();
    var b2 = modified.readU8();

    if (b1 !== b2) {
      var RLERecord = true;
      var differentBytes = [];
      var offset = modified.offset - 1;

      while (b1 !== b2 && differentBytes.length < 0xff) {
        differentBytes.push(b2);
        if (b2 !== differentBytes[0]) RLERecord = false;

        if (modified.isEOF() || differentBytes.length === 0xff) break;

        b1 = original.isEOF() ? 0x00 : original.readU8();
        b2 = modified.readU8();
      }

      if (RLERecord && differentBytes.length > 2) {
        patch.addRLERecord(offset, differentBytes[0], differentBytes.length);
      } else {
        patch.addRecord(offset, differentBytes);
      }
    }
  }

  return patch;
};
