/* PPF module for Rom Patcher JS v20200221 - Marc Robledo 2019-2020 - http://www.marcrobledo.com/license */
/* File format specification: https://www.romhacking.net/utilities/353/  */

const PPF_MAGIC = "PPF";
const PPF_IMAGETYPE_BIN = 0x00;
const PPF_IMAGETYPE_GI = 0x01;
const PPF_BEGIN_FILE_ID_DIZ_MAGIC = "@BEG"; //@BEGIN_FILE_ID.DIZ

if (typeof module !== "undefined" && module.exports) {
  module.exports = PPF;
}
function PPF() {
  this.version = 3;
  this.imageType = PPF_IMAGETYPE_BIN;
  this.blockCheck = false;
  this.undoData = false;
  this.records = [];
}
PPF.prototype.addRecord = function (offset, data, undoData) {
  if (this.undoData) {
    this.records.push({ offset: offset, data: data, undoData: undoData });
  } else {
    this.records.push({ offset: offset, data: data });
  }
};
PPF.prototype.toString = function () {
  var s = this.description;
  s += "\nPPF version: " + this.version;
  s += "\n#Records: " + this.records.length;
  s += "\nImage type: " + this.imageType;
  s += "\nBlock check: " + !!this.blockCheck;
  s += "\nUndo data: " + this.undoData;
  if (this.fileIdDiz) s += "\nFILE_ID.DIZ: " + this.fileIdDiz;
  return s;
};
PPF.prototype.export = function (fileName) {
  var patchFileSize = 5 + 1 + 50; //PPFx0
  for (var i = 0; i < this.records.length; i++) {
    patchFileSize += 4 + 1 + this.records[i].data.length;
    if (this.version === 3) patchFileSize += 4; //offsets are u64
  }

  if (this.version === 3 || this.version === 2) {
    patchFileSize += 4;
  }
  if (this.blockCheck) {
    patchFileSize += 1024;
  }
  if (this.fileIdDiz) {
    patchFileSize += 18 + this.fileIdDiz.length + 16 + 4;
  }

  tempFile = new BinFile(patchFileSize);
  tempFile.fileName = fileName + ".ppf";
  tempFile.writeString(PPF_MAGIC);
  tempFile.writeString((this.version * 10).toString());
  tempFile.writeU8(parseInt(this.version) - 1);
  tempFile.writeString(this.description, 50);

  if (this.version === 3) {
    tempFile.writeU8(this.imageType);
    tempFile.writeU8(this.blockCheck ? 0x01 : 0x00);
    tempFile.writeU8(this.undoData ? 0x01 : 0x00);
    tempFile.writeU8(0x00); //dummy
  } else if (this.version === 2) {
    tempFile.writeU32(this.inputFileSize);
  }

  if (this.blockCheck) {
    tempFile.writeBytes(this.blockCheck);
  }

  tempFile.littleEndian = true;
  for (var i = 0; i < this.records.length; i++) {
    tempFile.writeU32(this.records[i].offset & 0xffffffff);

    if (this.version === 3) {
      var offset2 = this.records[i].offset;
      for (var j = 0; j < 32; j++) offset2 = parseInt((offset2 / 2) >>> 0);
      tempFile.writeU32(offset2);
    }
    tempFile.writeU8(this.records[i].data.length);
    tempFile.writeBytes(this.records[i].data);
    if (this.undoData) tempFile.writeBytes(this.records[i].undoData);
  }

  if (this.fileIdDiz) {
    tempFile.writeString("@BEGIN_FILE_ID.DIZ");
    tempFile.writeString(this.fileIdDiz);
    tempFile.writeString("@END_FILE_ID.DIZ");
    tempFile.writeU16(this.fileIdDiz.length);
    tempFile.writeU16(0x00);
  }

  return tempFile;
};
PPF.prototype.apply = function (romFile) {
  var newFileSize = romFile.fileSize;
  for (var i = 0; i < this.records.length; i++) {
    if (this.records[i].offset + this.records[i].data.length > newFileSize)
      newFileSize = this.records[i].offset + this.records[i].data.length;
  }
  if (newFileSize === romFile.fileSize) {
    tempFile = romFile.slice(0, romFile.fileSize);
  } else {
    tempFile = new BinFile(newFileSize);
    romFile.copyTo(tempFile, 0);
  }

  //check if undoing
  var undoingData = false;
  if (this.undoData) {
    tempFile.seek(this.records[0].offset);
    var originalBytes = tempFile.readBytes(this.records[0].data.length);
    var foundDifferences = false;
    for (var i = 0; i < originalBytes.length && !foundDifferences; i++) {
      if (originalBytes[i] !== this.records[0].data[i]) {
        foundDifferences = true;
      }
    }
    if (!foundDifferences) {
      undoingData = true;
    }
  }

  for (var i = 0; i < this.records.length; i++) {
    tempFile.seek(this.records[i].offset);

    if (undoingData) {
      tempFile.writeBytes(this.records[i].undoData);
    } else {
      tempFile.writeBytes(this.records[i].data);
    }
  }

  return tempFile;
};

PPF.MAGIC = PPF_MAGIC;

PPF.fromFile = function (patchFile) {
  var patch = new PPF();

  patchFile.seek(3);
  var version1 = parseInt(patchFile.readString(2)) / 10;
  var version2 = patchFile.readU8() + 1;
  if (version1 !== version2 || version1 > 3) {
    throw new Error("invalid PPF version");
  }

  patch.version = version1;
  patch.description = patchFile.readString(50).replace(/ +$/, "");

  if (patch.version === 3) {
    patch.imageType = patchFile.readU8();
    if (patchFile.readU8()) patch.blockCheck = true;
    if (patchFile.readU8()) patch.undoData = true;

    patchFile.skip(1);
  } else if (patch.version === 2) {
    patch.blockCheck = true;
    patch.inputFileSize = patchFile.readU32();
  }

  if (patch.blockCheck) {
    patch.blockCheck = patchFile.readBytes(1024);
  }

  patchFile.littleEndian = true;
  while (!patchFile.isEOF()) {
    if (patchFile.readString(4) === PPF_BEGIN_FILE_ID_DIZ_MAGIC) {
      patchFile.skip(14);
      //console.log('found file_id.diz begin');
      patch.fileIdDiz = patchFile.readString(3072);
      patch.fileIdDiz = patch.fileIdDiz.substr(
        0,
        patch.fileIdDiz.indexOf("@END_FILE_ID.DIZ"),
      );
      break;
    }
    patchFile.skip(-4);

    var offset;
    if (patch.version === 3) {
      var u64_1 = patchFile.readU32();
      var u64_2 = patchFile.readU32();
      offset = u64_1 + u64_2 * 0x100000000;
    } else offset = patchFile.readU32();

    var len = patchFile.readU8();
    var data = patchFile.readBytes(len);

    var undoData = false;
    if (patch.undoData) {
      undoData = patchFile.readBytes(len);
    }

    patch.addRecord(offset, data, undoData);
  }

  return patch;
};

PPF.buildFromRoms = function (original, modified) {
  var patch = new PPF();

  patch.description = "Patch description";

  if (original.fileSize > modified.fileSize) {
    var expandedModified = new BinFile(original.fileSize);
    modified.copyTo(expandedModified, 0);
    modified = expandedModified;
  }

  original.seek(0);
  modified.seek(0);
  while (!modified.isEOF()) {
    var b1 = original.isEOF() ? 0x00 : original.readU8();
    var b2 = modified.readU8();

    if (b1 !== b2) {
      var differentData = [];
      var offset = modified.offset - 1;

      while (b1 !== b2 && differentData.length < 0xff) {
        differentData.push(b2);

        if (modified.isEOF() || differentData.length === 0xff) break;

        b1 = original.isEOF() ? 0x00 : original.readU8();
        b2 = modified.readU8();
      }

      patch.addRecord(offset, differentData);
    }
  }

  if (original.fileSize < modified.fileSize) {
    modified.seek(modified.fileSize - 1);
    if (modified.readU8() === 0x00)
      patch.addRecord(modified.fileSize - 1, [0x00]);
  }

  return patch;
};
