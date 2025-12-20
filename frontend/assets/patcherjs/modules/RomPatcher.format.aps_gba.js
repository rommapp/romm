/* APS (GBA) module for Rom Patcher JS v20230331 - Marc Robledo 2017-2023 - http://www.marcrobledo.com/license */
/* File format specification: https://github.com/btimofeev/UniPatcher/wiki/APS-(GBA) */

const APS_GBA_MAGIC = "APS1";
const APS_GBA_BLOCK_SIZE = 0x010000; //64Kb
const APS_GBA_RECORD_SIZE = 4 + 2 + 2 + APS_GBA_BLOCK_SIZE;
if (typeof module !== "undefined" && module.exports) {
  module.exports = APSGBA;
}
function APSGBA() {
  this.sourceSize = 0;
  this.targetSize = 0;
  this.records = [];
}
APSGBA.prototype.addRecord = function (
  offset,
  sourceCrc16,
  targetCrc16,
  xorBytes,
) {
  this.records.push({
    offset: offset,
    sourceCrc16: sourceCrc16,
    targetCrc16: targetCrc16,
    xorBytes: xorBytes,
  });
};
APSGBA.prototype.toString = function () {
  var s = "Total records: " + this.records.length;
  s += "\nInput file size: " + this.sourceSize;
  s += "\nOutput file size: " + this.targetSize;
  return s;
};
APSGBA.prototype.validateSource = function (sourceFile) {
  if (sourceFile.fileSize !== this.sourceSize) return false;

  for (var i = 0; i < this.records.length; i++) {
    sourceFile.seek(this.records[i].offset);
    var bytes = sourceFile.readBytes(APS_GBA_BLOCK_SIZE);
    if (
      sourceFile.hashCRC16(this.records[i].offset, APS_GBA_BLOCK_SIZE) !==
      this.records[i].sourceCrc16
    )
      return false;
  }

  return true;
};
APSGBA.prototype.export = function (fileName) {
  var patchFileSize = 12 + this.records.length * APS_GBA_RECORD_SIZE;

  tempFile = new BinFile(patchFileSize);
  tempFile.littleEndian = true;
  tempFile.fileName = fileName + ".aps";
  tempFile.writeString(APS_GBA_MAGIC, APS_GBA_MAGIC.length);
  tempFile.writeU32(this.sourceSize);
  tempFile.writeU32(this.targetSize);

  for (var i = 0; i < this.records.length; i++) {
    tempFile.writeU32(this.records[i].offset);
    tempFile.writeU16(this.records[i].sourceCrc16);
    tempFile.writeU16(this.records[i].targetCrc16);
    tempFile.writeBytes(this.records[i].xorBytes);
  }

  return tempFile;
};

APSGBA.prototype.apply = function (romFile, validate) {
  if (validate && !this.validateSource(romFile)) {
    throw new Error("Source ROM checksum mismatch");
  }

  tempFile = new BinFile(this.targetSize);
  romFile.copyTo(tempFile, 0, romFile.fileSize);

  for (var i = 0; i < this.records.length; i++) {
    romFile.seek(this.records[i].offset);
    tempFile.seek(this.records[i].offset);
    for (var j = 0; j < APS_GBA_BLOCK_SIZE; j++) {
      tempFile.writeU8(romFile.readU8() ^ this.records[i].xorBytes[j]);
    }

    if (
      validate &&
      tempFile.hashCRC16(this.records[i].offset, APS_GBA_BLOCK_SIZE) !==
        this.records[i].targetCrc16
    ) {
      throw new Error("Target ROM checksum mismatch");
    }
  }

  return tempFile;
};

APSGBA.MAGIC = APS_GBA_MAGIC;

APSGBA.fromFile = function (patchFile) {
  patchFile.seek(0);
  patchFile.littleEndian = true;

  if (
    patchFile.readString(APS_GBA_MAGIC.length) !== APS_GBA_MAGIC ||
    patchFile.fileSize < 12 + APS_GBA_RECORD_SIZE ||
    (patchFile.fileSize - 12) % APS_GBA_RECORD_SIZE !== 0
  )
    return null;

  var patch = new APSGBA();

  patch.sourceSize = patchFile.readU32();
  patch.targetSize = patchFile.readU32();

  while (!patchFile.isEOF()) {
    var offset = patchFile.readU32();
    var sourceCrc16 = patchFile.readU16();
    var targetCrc16 = patchFile.readU16();
    var xorBytes = patchFile.readBytes(APS_GBA_BLOCK_SIZE);

    patch.addRecord(offset, sourceCrc16, targetCrc16, xorBytes);
  }
  return patch;
};
