/* UPS module for Rom Patcher JS v20240721 - Marc Robledo 2017-2024 - http://www.marcrobledo.com/license */
/* File format specification: http://www.romhacking.net/documents/392/ */

const UPS_MAGIC = "UPS1";
if (typeof module !== "undefined" && module.exports) {
  module.exports = UPS;
}
function UPS() {
  this.records = [];
  this.sizeInput = 0;
  this.sizeOutput = 0;
  this.checksumInput = 0;
  this.checksumOutput = 0;
}
UPS.prototype.addRecord = function (relativeOffset, d) {
  this.records.push({ offset: relativeOffset, XORdata: d });
};
UPS.prototype.toString = function () {
  var s = "Records: " + this.records.length;
  s += "\nInput file size: " + this.sizeInput;
  s += "\nOutput file size: " + this.sizeOutput;
  s += "\nInput file checksum: " + this.checksumInput.toString(16);
  s += "\nOutput file checksum: " + this.checksumOutput.toString(16);
  return s;
};
UPS.prototype.export = function (fileName) {
  var patchFileSize = UPS_MAGIC.length; //UPS1 string
  patchFileSize += UPS_getVLVLength(this.sizeInput); //input file size
  patchFileSize += UPS_getVLVLength(this.sizeOutput); //output file size
  for (var i = 0; i < this.records.length; i++) {
    patchFileSize += UPS_getVLVLength(this.records[i].offset);
    patchFileSize += this.records[i].XORdata.length + 1;
  }
  patchFileSize += 12; //input/output/patch checksums

  tempFile = new BinFile(patchFileSize);
  tempFile.writeVLV = UPS_writeVLV;
  tempFile.fileName = fileName + ".ups";
  tempFile.writeString(UPS_MAGIC);

  tempFile.writeVLV(this.sizeInput);
  tempFile.writeVLV(this.sizeOutput);

  for (var i = 0; i < this.records.length; i++) {
    tempFile.writeVLV(this.records[i].offset);
    tempFile.writeBytes(this.records[i].XORdata);
    tempFile.writeU8(0x00);
  }
  tempFile.littleEndian = true;
  tempFile.writeU32(this.checksumInput);
  tempFile.writeU32(this.checksumOutput);
  tempFile.writeU32(tempFile.hashCRC32(0, tempFile.fileSize - 4));

  return tempFile;
};
UPS.prototype.validateSource = function (romFile, headerSize) {
  return romFile.hashCRC32(headerSize) === this.checksumInput;
};
UPS.prototype.getValidationInfo = function () {
  return {
    type: "CRC32",
    value: this.checksumInput,
  };
};
UPS.prototype.apply = function (romFile, validate) {
  if (validate && !this.validateSource(romFile)) {
    throw new Error("Source ROM checksum mismatch");
  }

  /* fix the glitch that cut the end of the file if it's larger than the changed file patch was originally created with */
  /* more info: https://github.com/marcrobledo/RomPatcher.js/pull/40#issuecomment-1069087423 */
  sizeOutput = this.sizeOutput;
  sizeInput = this.sizeInput;
  if (!validate && sizeInput < romFile.fileSize) {
    sizeInput = romFile.fileSize;
    if (sizeOutput < sizeInput) {
      sizeOutput = sizeInput;
    }
  }

  /* copy original file */
  tempFile = new BinFile(sizeOutput);
  romFile.copyTo(tempFile, 0, sizeInput);

  romFile.seek(0);

  var nextOffset = 0;
  for (var i = 0; i < this.records.length; i++) {
    var record = this.records[i];
    tempFile.skip(record.offset);
    romFile.skip(record.offset);

    for (var j = 0; j < record.XORdata.length; j++) {
      tempFile.writeU8(
        (romFile.isEOF() ? 0x00 : romFile.readU8()) ^ record.XORdata[j],
      );
    }
    tempFile.skip(1);
    romFile.skip(1);
  }

  if (validate && tempFile.hashCRC32() !== this.checksumOutput) {
    throw new Error("Target ROM checksum mismatch");
  }

  return tempFile;
};

UPS.MAGIC = UPS_MAGIC;

/* encode/decode variable length values, used by UPS file structure */
function UPS_writeVLV(data) {
  while (1) {
    var x = data & 0x7f;
    data = data >> 7;
    if (data === 0) {
      this.writeU8(0x80 | x);
      break;
    }
    this.writeU8(x);
    data = data - 1;
  }
}
function UPS_readVLV() {
  var data = 0;

  var shift = 1;
  while (1) {
    var x = this.readU8();

    if (x == -1)
      throw new Error(
        "Can't read UPS VLV at 0x" + (this.offset - 1).toString(16),
      );

    data += (x & 0x7f) * shift;
    if ((x & 0x80) !== 0) break;
    shift = shift << 7;
    data += shift;
  }
  return data;
}
function UPS_getVLVLength(data) {
  var len = 0;
  while (1) {
    var x = data & 0x7f;
    data = data >> 7;
    len++;
    if (data === 0) {
      break;
    }
    data = data - 1;
  }
  return len;
}

UPS.fromFile = function (file) {
  var patch = new UPS();
  file.readVLV = UPS_readVLV;

  file.seek(UPS_MAGIC.length);

  patch.sizeInput = file.readVLV();
  patch.sizeOutput = file.readVLV();

  var nextOffset = 0;
  while (file.offset < file.fileSize - 12) {
    var relativeOffset = file.readVLV();

    var XORdifferences = [];
    while (file.readU8()) {
      XORdifferences.push(file._lastRead);
    }
    patch.addRecord(relativeOffset, XORdifferences);
  }

  file.littleEndian = true;
  patch.checksumInput = file.readU32();
  patch.checksumOutput = file.readU32();

  if (file.readU32() !== file.hashCRC32(0, file.fileSize - 4)) {
    throw new Error("Patch checksum mismatch");
  }

  file.littleEndian = false;
  return patch;
};

UPS.buildFromRoms = function (original, modified) {
  var patch = new UPS();
  patch.sizeInput = original.fileSize;
  patch.sizeOutput = modified.fileSize;

  var previousSeek = 1;
  while (!modified.isEOF()) {
    var b1 = original.isEOF() ? 0x00 : original.readU8();
    var b2 = modified.readU8();

    if (b1 !== b2) {
      var currentSeek = modified.offset;
      var XORdata = [];

      while (b1 !== b2) {
        XORdata.push(b1 ^ b2);

        if (modified.isEOF()) break;
        b1 = original.isEOF() ? 0x00 : original.readU8();
        b2 = modified.readU8();
      }

      patch.addRecord(currentSeek - previousSeek, XORdata);
      previousSeek = currentSeek + XORdata.length + 1;
    }
  }

  patch.checksumInput = original.hashCRC32();
  patch.checksumOutput = modified.hashCRC32();
  return patch;
};
