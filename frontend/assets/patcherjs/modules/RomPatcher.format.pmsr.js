/* PMSR (Paper Mario Star Rod) module for Rom Patcher JS v20240721 - Marc Robledo 2020-2024 - http://www.marcrobledo.com/license */
/* File format specification: http://origami64.net/attachment.php?aid=790 (dead link) */

const PMSR_MAGIC = "PMSR";
const YAY0_MAGIC = "Yay0";
const PAPER_MARIO_USA10_CRC32 = 0xa7f5cd7e;
const PAPER_MARIO_USA10_FILE_SIZE = 41943040;
if (typeof module !== "undefined" && module.exports) {
  module.exports = PMSR;
}

function PMSR() {
  this.targetSize = 0;
  this.records = [];
}
PMSR.prototype.addRecord = function (offset, data) {
  this.records.push({ offset: offset, data: data });
};
PMSR.prototype.toString = function () {
  var s = "Star Rod patch";
  s += "\nTarget file size: " + this.targetSize;
  s += "\n#Records: " + this.records.length;
  return s;
};

PMSR.prototype.validateSource = function (romFile) {
  return (
    romFile.fileSize === PAPER_MARIO_USA10_FILE_SIZE &&
    romFile.hashCRC32() === PAPER_MARIO_USA10_CRC32
  );
};
PMSR.prototype.getValidationInfo = function () {
  return {
    type: "CRC32",
    value: PAPER_MARIO_USA10_CRC32,
  };
};
PMSR.prototype.apply = function (romFile, validate) {
  if (validate && !this.validateSource(romFile)) {
    throw new Error("Source ROM checksum mismatch");
  }

  console.log("a");
  if (this.targetSize === romFile.fileSize) {
    tempFile = romFile.slice(0, romFile.fileSize);
  } else {
    tempFile = new BinFile(this.targetSize);
    romFile.copyTo(tempFile, 0);
  }

  console.log("b");
  for (var i = 0; i < this.records.length; i++) {
    tempFile.seek(this.records[i].offset);
    tempFile.writeBytes(this.records[i].data);
  }

  return tempFile;
};

PMSR.MAGIC = PMSR_MAGIC;

PMSR.fromFile = function (file) {
  var patch = new PMSR();

  /*file.seek(0);
	if(file.readString(YAY0_MAGIC.length)===YAY0_MAGIC){
		file=PMSR.YAY0_decode(file);
	}*/

  patch.targetSize = PAPER_MARIO_USA10_FILE_SIZE;

  file.seek(4);
  var nRecords = file.readU32();

  for (var i = 0; i < nRecords; i++) {
    var offset = file.readU32();
    var length = file.readU32();
    patch.addRecord(offset, file.readBytes(length));

    if (offset + length > patch.targetSize) patch.targetSize = offset + length;
  }

  return patch;
};

/* to-do */
//PMSR.prototype.export=function(fileName){return null}
//PMSR.buildFromRoms=function(original, modified){return null}

/* https://github.com/pho/WindViewer/wiki/Yaz0-and-Yay0 */
PMSR.YAY0_decode = function (file) {
  /* to-do */
};
