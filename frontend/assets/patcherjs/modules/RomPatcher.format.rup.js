/* RUP module for Rom Patcher JS v20250430 - Marc Robledo 2018-2025 - http://www.marcrobledo.com/license */
/* File format specification: http://www.romhacking.net/documents/288/ */

const RUP_MAGIC = "NINJA2";
const RUP_COMMAND_END = 0x00;
const RUP_COMMAND_OPEN_NEW_FILE = 0x01;
const RUP_COMMAND_XOR_RECORD = 0x02;
const RUP_ROM_TYPES = [
  "raw",
  "nes",
  "fds",
  "snes",
  "n64",
  "gb",
  "sms",
  "mega",
  "pce",
  "lynx",
];
if (typeof module !== "undefined" && module.exports) {
  module.exports = RUP;
}

function RUP() {
  this.author = "";
  this.version = "";
  this.title = "";
  this.genre = "";
  this.language = "";
  this.date = "";
  this.web = "";
  this.description = "";
  this.files = [];
}
RUP.prototype.toString = function () {
  var s = "Author: " + this.author;
  s += "\nVersion: " + this.version;
  s += "\nTitle: " + this.title;
  s += "\nGenre: " + this.genre;
  s += "\nLanguage: " + this.language;
  s += "\nDate: " + this.date;
  s += "\nWeb: " + this.web;
  s += "\nDescription: " + this.description;
  for (var i = 0; i < this.files.length; i++) {
    var file = this.files[i];
    s += "\n---------------";
    s += "\nFile " + i + ":";
    s += "\nFile name: " + file.fileName;
    s += "\nRom type: " + RUP_ROM_TYPES[file.romType];
    s += "\nSource file size: " + file.sourceFileSize;
    s += "\nTarget file size: " + file.targetFileSize;
    s += "\nSource MD5: " + file.sourceMD5;
    s += "\nTarget MD5: " + file.targetMD5;
    if (file.overflowMode === "A") {
      s += "\nOverflow mode: Append " + file.overflowData.length + " bytes";
    } else if (file.overflowMode === "M") {
      s += "\nOverflow mode: Minify " + file.overflowData.length + " bytes";
    }
    s += "\n#records: " + file.records.length;
  }
  return s;
};

RUP.prototype.validateSource = function (romFile, headerSize) {
  var md5string = romFile.hashMD5(headerSize);
  for (var i = 0; i < this.files.length; i++) {
    if (
      this.files[i].sourceMD5 === md5string ||
      this.files[i].targetMD5 === md5string
    ) {
      return {
        file: this.files[i],
        undo: this.files[i].targetMD5 === md5string,
      };
    }
  }
  return false;
};
RUP.prototype.getValidationInfo = function () {
  var values = [];
  for (var i = 0; i < this.files.length; i++) {
    values.push(this.files[i].sourceMD5);
  }
  return {
    type: "MD5",
    value: values,
  };
};
RUP.prototype.getDescription = function () {
  return this.description ? this.description : null;
};
RUP.prototype.apply = function (romFile, validate) {
  var validFile;
  if (validate) {
    validFile = this.validateSource(romFile);

    if (!validFile) throw new Error("Source ROM checksum mismatch");
  } else {
    validFile = {
      file: this.files[0],
      undo: this.files[0].targetMD5 === romFile.hashMD5(),
    };
  }

  var undo = validFile.undo;
  var patch = validFile.file;

  tempFile = new BinFile(!undo ? patch.targetFileSize : patch.sourceFileSize);
  /* copy original file */
  romFile.copyTo(tempFile, 0);

  for (var i = 0; i < patch.records.length; i++) {
    var offset = patch.records[i].offset;
    romFile.seek(offset);
    tempFile.seek(offset);
    for (var j = 0; j < patch.records[i].xor.length; j++) {
      tempFile.writeU8(
        (romFile.isEOF() ? 0x00 : romFile.readU8()) ^ patch.records[i].xor[j],
      );
    }
  }

  /* add overflow data if needed */
  if (patch.overflowMode === "A" && !undo) {
    /* append */
    tempFile.seek(patch.sourceFileSize);
    tempFile.writeBytes(patch.overflowData.map((byte) => byte ^ 0xff));
  } else if (patch.overflowMode === "M" && undo) {
    /* minify */
    tempFile.seek(patch.targetFileSize);
    tempFile.writeBytes(patch.overflowData.map((byte) => byte ^ 0xff));
  }

  if (
    validate &&
    ((!undo && tempFile.hashMD5() !== patch.targetMD5) ||
      (undo && tempFile.hashMD5() !== patch.sourceMD5))
  ) {
    throw new Error("Target ROM checksum mismatch");
  }

  if (undo) tempFile.unpatched = true;

  return tempFile;
};

RUP.MAGIC = RUP_MAGIC;

RUP.padZeroes = function (intVal, nBytes) {
  var hexString = intVal.toString(16);
  while (hexString.length < nBytes * 2) hexString = "0" + hexString;
  return hexString;
};
RUP.fromFile = function (file) {
  var patch = new RUP();
  file.readVLV = RUP_readVLV;

  file.seek(RUP_MAGIC.length);

  patch.textEncoding = file.readU8();
  patch.author = file.readString(84);
  patch.version = file.readString(11);
  patch.title = file.readString(256);
  patch.genre = file.readString(48);
  patch.language = file.readString(48);
  patch.date = file.readString(8);
  patch.web = file.readString(512);
  patch.description = file.readString(1074).replace(/\\n/g, "\n");

  file.seek(0x800);
  var nextFile;
  while (!file.isEOF()) {
    var command = file.readU8();

    if (command === RUP_COMMAND_OPEN_NEW_FILE) {
      if (nextFile) patch.files.push(nextFile);

      nextFile = {
        records: [],
      };

      nextFile.fileName = file.readString(file.readVLV());
      nextFile.romType = file.readU8();
      nextFile.sourceFileSize = file.readVLV();
      nextFile.targetFileSize = file.readVLV();

      nextFile.sourceMD5 = "";
      for (var i = 0; i < 16; i++)
        nextFile.sourceMD5 += RUP.padZeroes(file.readU8(), 1);

      nextFile.targetMD5 = "";
      for (var i = 0; i < 16; i++)
        nextFile.targetMD5 += RUP.padZeroes(file.readU8(), 1);

      if (nextFile.sourceFileSize !== nextFile.targetFileSize) {
        nextFile.overflowMode = file.readString(1); // 'M' (source>target) or 'A' (source<target)
        if (nextFile.overflowMode !== "M" && nextFile.overflowMode !== "A")
          throw new Error("RUP: invalid overflow mode");
        nextFile.overflowData = file.readBytes(file.readVLV());
      }
    } else if (command === RUP_COMMAND_XOR_RECORD) {
      nextFile.records.push({
        offset: file.readVLV(),
        xor: file.readBytes(file.readVLV()),
      });
    } else if (command === RUP_COMMAND_END) {
      if (nextFile) patch.files.push(nextFile);
      break;
    } else {
      throw new Error("invalid RUP command");
    }
  }
  return patch;
};

function RUP_readVLV() {
  var nBytes = this.readU8();
  var data = 0;
  for (var i = 0; i < nBytes; i++) {
    data += this.readU8() << (i * 8);
  }
  return data;
}
function RUP_writeVLV(data) {
  var len = RUP_getVLVLen(data) - 1;

  this.writeU8(len);

  while (data) {
    this.writeU8(data & 0xff);
    data >>= 8;
  }
}
function RUP_getVLVLen(data) {
  var ret = 1;
  while (data) {
    ret++;
    data >>= 8;
  }
  return ret;
}

RUP.prototype.export = function (fileName) {
  var patchFileSize = 2048;
  for (var i = 0; i < this.files.length; i++) {
    var file = this.files[i];
    patchFileSize++; //command 0x01

    patchFileSize += RUP_getVLVLen(file.fileName.length);
    patchFileSize += file.fileName.length;
    patchFileSize++; //rom type
    patchFileSize += RUP_getVLVLen(file.sourceFileSize);
    patchFileSize += RUP_getVLVLen(file.targetFileSize);
    patchFileSize += 32; //MD5s

    if (file.sourceFileSize !== file.targetFileSize) {
      patchFileSize++; // M or A
      patchFileSize += RUP_getVLVLen(file.overflowData.length);
      patchFileSize += file.overflowData.length;
    }
    for (var j = 0; j < file.records.length; j++) {
      patchFileSize++; //command 0x01
      patchFileSize += RUP_getVLVLen(file.records[j].offset);
      patchFileSize += RUP_getVLVLen(file.records[j].xor.length);
      patchFileSize += file.records[j].xor.length;
    }
  }
  patchFileSize++; //command 0x00

  var patchFile = new BinFile(patchFileSize);
  patchFile.fileName = fileName + ".rup";
  patchFile.writeVLV = RUP_writeVLV;

  patchFile.writeString(RUP_MAGIC);
  patchFile.writeU8(this.textEncoding);
  patchFile.writeString(this.author, 84);
  patchFile.writeString(this.version, 11);
  patchFile.writeString(this.title, 256);
  patchFile.writeString(this.genre, 48);
  patchFile.writeString(this.language, 48);
  patchFile.writeString(this.date, 8);
  patchFile.writeString(this.web, 512);
  patchFile.writeString(this.description.replace(/\n/g, "\\n"), 1074);

  for (var i = 0; i < this.files.length; i++) {
    var file = this.files[i];
    patchFile.writeU8(RUP_COMMAND_OPEN_NEW_FILE);

    patchFile.writeVLV(file.fileName);
    patchFile.writeU8(file.romType);
    patchFile.writeVLV(file.sourceFileSize);
    patchFile.writeVLV(file.targetFileSize);

    for (var j = 0; j < 16; j++)
      patchFile.writeU8(parseInt(file.sourceMD5.substr(j * 2, 2), 16));
    for (var j = 0; j < 16; j++)
      patchFile.writeU8(parseInt(file.targetMD5.substr(j * 2, 2), 16));

    if (file.sourceFileSize !== file.targetFileSize) {
      patchFile.writeString(
        file.sourceFileSize > file.targetFileSize ? "M" : "A",
      );
      patchFile.writeVLV(file.overflowData.length);
      patchFile.writeBytes(file.overflowData);
    }

    for (var j = 0; j < file.records.length; j++) {
      patchFile.writeU8(RUP_COMMAND_XOR_RECORD);

      patchFile.writeVLV(file.records[j].offset);
      patchFile.writeVLV(file.records[j].xor.length);
      patchFile.writeBytes(file.records[j].xor);
    }
  }

  patchFile.writeU8(RUP_COMMAND_END);

  return patchFile;
};

RUP.buildFromRoms = function (original, modified, description) {
  var patch = new RUP();

  var today = new Date();
  patch.date =
    today.getYear() +
    1900 +
    RUP.padZeroes(today.getMonth() + 1, 1) +
    RUP.padZeroes(today.getDate(), 1);
  if (description) patch.description = description;

  var file = {
    fileName: "",
    romType: 0,
    sourceFileSize: original.fileSize,
    targetFileSize: modified.fileSize,
    sourceMD5: original.hashMD5(),
    targetMD5: modified.hashMD5(),
    overflowMode: null,
    overflowData: [],
    records: [],
  };

  if (file.sourceFileSize < file.targetFileSize) {
    modified.seek(file.sourceFileSize);
    file.overflowMode = "A";
    file.overflowData = modified
      .readBytes(file.targetFileSize - file.sourceFileSize)
      .map((byte) => byte ^ 0xff);
    modified = modified.slice(0, file.sourceFileSize);
  } else if (file.sourceFileSize > file.targetFileSize) {
    original.seek(file.targetFileSize);
    file.overflowMode = "M";
    file.overflowData = original
      .readBytes(file.sourceFileSize - file.targetFileSize)
      .map((byte) => byte ^ 0xff);
    original = original.slice(0, file.targetFileSize);
  }

  original.seek(0);
  modified.seek(0);

  while (!modified.isEOF()) {
    var b1 = original.isEOF() ? 0x00 : original.readU8();
    var b2 = modified.readU8();

    if (b1 !== b2) {
      var originalOffset = modified.offset - 1;
      var xorDifferences = [];

      while (b1 !== b2) {
        xorDifferences.push(b1 ^ b2);

        if (modified.isEOF()) break;

        b1 = original.isEOF() ? 0x00 : original.readU8();
        b2 = modified.readU8();
      }

      file.records.push({ offset: originalOffset, xor: xorDifferences });
    }
  }

  patch.files.push(file);

  return patch;
};
