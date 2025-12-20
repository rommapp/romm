/* BPS module for Rom Patcher JS v20240821 - Marc Robledo 2016-2024 - http://www.marcrobledo.com/license */
/* File format specification: https://www.romhacking.net/documents/746/ */

const BPS_MAGIC = "BPS1";
const BPS_ACTION_SOURCE_READ = 0;
const BPS_ACTION_TARGET_READ = 1;
const BPS_ACTION_SOURCE_COPY = 2;
const BPS_ACTION_TARGET_COPY = 3;
if (typeof module !== "undefined" && module.exports) {
  module.exports = BPS;
}

function BPS() {
  this.sourceSize = 0;
  this.targetSize = 0;
  this.metaData = "";
  this.actions = [];
  this.sourceChecksum = 0;
  this.targetChecksum = 0;
  this.patchChecksum = 0;
}
BPS.prototype.toString = function () {
  var s = "Source size: " + this.sourceSize;
  s += "\nTarget size: " + this.targetSize;
  s += "\nMetadata: " + this.metaData;
  s += "\n#Actions: " + this.actions.length;
  return s;
};
BPS.prototype.calculateFileChecksum = function () {
  var patchFile = this.export();
  return patchFile.hashCRC32(0, patchFile.fileSize - 4);
};
BPS.prototype.validateSource = function (romFile, headerSize) {
  return this.sourceChecksum === romFile.hashCRC32(headerSize);
};
BPS.prototype.getValidationInfo = function () {
  return {
    type: "CRC32",
    value: this.sourceChecksum,
  };
};
BPS.prototype.apply = function (romFile, validate) {
  if (validate && !this.validateSource(romFile)) {
    throw new Error("Source ROM checksum mismatch");
  }

  tempFile = new BinFile(this.targetSize);

  //patch
  var sourceRelativeOffset = 0;
  var targetRelativeOffset = 0;
  for (var i = 0; i < this.actions.length; i++) {
    var action = this.actions[i];

    if (action.type === BPS_ACTION_SOURCE_READ) {
      romFile.copyTo(tempFile, tempFile.offset, action.length);
      tempFile.skip(action.length);
    } else if (action.type === BPS_ACTION_TARGET_READ) {
      tempFile.writeBytes(action.bytes);
    } else if (action.type === BPS_ACTION_SOURCE_COPY) {
      sourceRelativeOffset += action.relativeOffset;
      var actionLength = action.length;
      while (actionLength--) {
        tempFile.writeU8(romFile._u8array[sourceRelativeOffset]);
        sourceRelativeOffset++;
      }
    } else if (action.type === BPS_ACTION_TARGET_COPY) {
      targetRelativeOffset += action.relativeOffset;
      var actionLength = action.length;
      while (actionLength--) {
        tempFile.writeU8(tempFile._u8array[targetRelativeOffset]);
        targetRelativeOffset++;
      }
    }
  }

  if (validate && this.targetChecksum !== tempFile.hashCRC32()) {
    throw new Error("Target ROM checksum mismatch");
  }

  return tempFile;
};

BPS.MAGIC = BPS_MAGIC;

BPS.fromFile = function (file) {
  file.readVLV = BPS_readVLV;

  file.littleEndian = true;
  var patch = new BPS();

  file.seek(4); //skip BPS1

  patch.sourceSize = file.readVLV();
  patch.targetSize = file.readVLV();

  var metaDataLength = file.readVLV();
  if (metaDataLength) {
    patch.metaData = file.readString(metaDataLength);
  }

  var endActionsOffset = file.fileSize - 12;
  while (file.offset < endActionsOffset) {
    var data = file.readVLV();
    var action = { type: data & 3, length: (data >> 2) + 1 };

    if (action.type === BPS_ACTION_TARGET_READ) {
      action.bytes = file.readBytes(action.length);
    } else if (
      action.type === BPS_ACTION_SOURCE_COPY ||
      action.type === BPS_ACTION_TARGET_COPY
    ) {
      var relativeOffset = file.readVLV();
      action.relativeOffset =
        (relativeOffset & 1 ? -1 : +1) * (relativeOffset >> 1);
    }

    patch.actions.push(action);
  }

  //file.seek(endActionsOffset);
  patch.sourceChecksum = file.readU32();
  patch.targetChecksum = file.readU32();
  patch.patchChecksum = file.readU32();

  if (patch.patchChecksum !== patch.calculateFileChecksum()) {
    throw new Error("Patch checksum mismatch");
  }

  return patch;
};

function BPS_readVLV() {
  var data = 0,
    shift = 1;
  while (true) {
    var x = this.readU8();
    data += (x & 0x7f) * shift;
    if (x & 0x80) break;
    shift <<= 7;
    data += shift;
  }

  this._lastRead = data;
  return data;
}
function BPS_writeVLV(data) {
  while (true) {
    var x = data & 0x7f;
    data >>= 7;
    if (data === 0) {
      this.writeU8(0x80 | x);
      break;
    }
    this.writeU8(x);
    data--;
  }
}
function BPS_getVLVLen(data) {
  var len = 0;
  while (true) {
    var x = data & 0x7f;
    data >>= 7;
    if (data === 0) {
      len++;
      break;
    }
    len++;
    data--;
  }
  return len;
}

BPS.prototype.export = function (fileName) {
  var patchFileSize = BPS_MAGIC.length;
  patchFileSize += BPS_getVLVLen(this.sourceSize);
  patchFileSize += BPS_getVLVLen(this.targetSize);
  patchFileSize += BPS_getVLVLen(this.metaData.length);
  patchFileSize += this.metaData.length;
  for (var i = 0; i < this.actions.length; i++) {
    var action = this.actions[i];
    patchFileSize += BPS_getVLVLen(((action.length - 1) << 2) + action.type);

    if (action.type === BPS_ACTION_TARGET_READ) {
      patchFileSize += action.length;
    } else if (
      action.type === BPS_ACTION_SOURCE_COPY ||
      action.type === BPS_ACTION_TARGET_COPY
    ) {
      patchFileSize += BPS_getVLVLen(
        (Math.abs(action.relativeOffset) << 1) +
          (action.relativeOffset < 0 ? 1 : 0),
      );
    }
  }
  patchFileSize += 12;

  var patchFile = new BinFile(patchFileSize);
  patchFile.fileName = fileName + ".bps";
  patchFile.littleEndian = true;
  patchFile.writeVLV = BPS_writeVLV;

  patchFile.writeString(BPS_MAGIC);
  patchFile.writeVLV(this.sourceSize);
  patchFile.writeVLV(this.targetSize);
  patchFile.writeVLV(this.metaData.length);
  patchFile.writeString(this.metaData, this.metaData.length);

  for (var i = 0; i < this.actions.length; i++) {
    var action = this.actions[i];
    patchFile.writeVLV(((action.length - 1) << 2) + action.type);

    if (action.type === BPS_ACTION_TARGET_READ) {
      patchFile.writeBytes(action.bytes);
    } else if (
      action.type === BPS_ACTION_SOURCE_COPY ||
      action.type === BPS_ACTION_TARGET_COPY
    ) {
      patchFile.writeVLV(
        (Math.abs(action.relativeOffset) << 1) +
          (action.relativeOffset < 0 ? 1 : 0),
      );
    }
  }
  patchFile.writeU32(this.sourceChecksum);
  patchFile.writeU32(this.targetChecksum);
  patchFile.writeU32(this.patchChecksum);

  return patchFile;
};

function BPS_Node() {
  this.offset = 0;
  this.next = null;
}
BPS_Node.prototype.delete = function () {
  if (this.next) delete this.next;
};
BPS.buildFromRoms = function (original, modified, deltaMode) {
  var patch = new BPS();
  patch.sourceSize = original.fileSize;
  patch.targetSize = modified.fileSize;

  if (deltaMode) {
    patch.actions = createBPSFromFilesDelta(original, modified);
  } else {
    patch.actions = createBPSFromFilesLinear(original, modified);
  }

  patch.sourceChecksum = original.hashCRC32();
  patch.targetChecksum = modified.hashCRC32();
  patch.patchChecksum = patch.calculateFileChecksum();
  return patch;
};

/* delta implementation from https://github.com/chiya/beat/blob/master/nall/beat/linear.hpp */
function createBPSFromFilesLinear(original, modified) {
  var patchActions = [];

  /* references to match original beat code */
  var sourceData = original._u8array;
  var targetData = modified._u8array;
  var sourceSize = original.fileSize;
  var targetSize = modified.fileSize;
  var Granularity = 1;

  var targetRelativeOffset = 0;
  var outputOffset = 0;
  var targetReadLength = 0;

  function targetReadFlush() {
    if (targetReadLength) {
      //encode(TargetRead | ((targetReadLength - 1) << 2));
      var action = {
        type: BPS_ACTION_TARGET_READ,
        length: targetReadLength,
        bytes: [],
      };
      patchActions.push(action);
      var offset = outputOffset - targetReadLength;
      while (targetReadLength) {
        //write(targetData[offset++]);
        action.bytes.push(targetData[offset++]);
        targetReadLength--;
      }
    }
  }

  while (outputOffset < targetSize) {
    var sourceLength = 0;
    for (var n = 0; outputOffset + n < Math.min(sourceSize, targetSize); n++) {
      if (sourceData[outputOffset + n] != targetData[outputOffset + n]) break;
      sourceLength++;
    }

    var rleLength = 0;
    for (var n = 1; outputOffset + n < targetSize; n++) {
      if (targetData[outputOffset] != targetData[outputOffset + n]) break;
      rleLength++;
    }

    if (rleLength >= 4) {
      //write byte to repeat
      targetReadLength++;
      outputOffset++;
      targetReadFlush();

      //copy starting from repetition byte
      //encode(TargetCopy | ((rleLength - 1) << 2));
      var relativeOffset = outputOffset - 1 - targetRelativeOffset;
      //encode(relativeOffset << 1);
      patchActions.push({
        type: BPS_ACTION_TARGET_COPY,
        length: rleLength,
        relativeOffset: relativeOffset,
      });
      outputOffset += rleLength;
      targetRelativeOffset = outputOffset - 1;
    } else if (sourceLength >= 4) {
      targetReadFlush();
      //encode(SourceRead | ((sourceLength - 1) << 2));
      patchActions.push({ type: BPS_ACTION_SOURCE_READ, length: sourceLength });
      outputOffset += sourceLength;
    } else {
      targetReadLength += Granularity;
      outputOffset += Granularity;
    }
  }

  targetReadFlush();

  return patchActions;
}

/* delta implementation from https://github.com/chiya/beat/blob/master/nall/beat/delta.hpp */
function createBPSFromFilesDelta(original, modified) {
  var patchActions = [];

  /* references to match original beat code */
  var sourceData = original._u8array;
  var targetData = modified._u8array;
  var sourceSize = original.fileSize;
  var targetSize = modified.fileSize;
  var Granularity = 1;

  var sourceRelativeOffset = 0;
  var targetRelativeOffset = 0;
  var outputOffset = 0;

  var sourceTree = new Array(65536);
  var targetTree = new Array(65536);
  for (var n = 0; n < 65536; n++) {
    sourceTree[n] = null;
    targetTree[n] = null;
  }

  //source tree creation
  for (var offset = 0; offset < sourceSize; offset++) {
    var symbol = sourceData[offset + 0];
    //sourceChecksum = crc32_adjust(sourceChecksum, symbol);
    if (offset < sourceSize - 1) symbol |= sourceData[offset + 1] << 8;
    var node = new BPS_Node();
    node.offset = offset;
    node.next = sourceTree[symbol];
    sourceTree[symbol] = node;
  }

  var targetReadLength = 0;

  function targetReadFlush() {
    if (targetReadLength) {
      //encode(TargetRead | ((targetReadLength - 1) << 2));
      var action = {
        type: BPS_ACTION_TARGET_READ,
        length: targetReadLength,
        bytes: [],
      };
      patchActions.push(action);
      var offset = outputOffset - targetReadLength;
      while (targetReadLength) {
        //write(targetData[offset++]);
        action.bytes.push(targetData[offset++]);
        targetReadLength--;
      }
    }
  }

  while (outputOffset < modified.fileSize) {
    var maxLength = 0,
      maxOffset = 0,
      mode = BPS_ACTION_TARGET_READ;

    var symbol = targetData[outputOffset + 0];
    if (outputOffset < targetSize - 1)
      symbol |= targetData[outputOffset + 1] << 8;

    {
      //source read
      var length = 0,
        offset = outputOffset;
      while (
        offset < sourceSize &&
        offset < targetSize &&
        sourceData[offset] == targetData[offset]
      ) {
        length++;
        offset++;
      }
      if (length > maxLength)
        ((maxLength = length), (mode = BPS_ACTION_SOURCE_READ));
    }

    {
      //source copy
      var node = sourceTree[symbol];
      while (node) {
        var length = 0,
          x = node.offset,
          y = outputOffset;
        while (
          x < sourceSize &&
          y < targetSize &&
          sourceData[x++] == targetData[y++]
        )
          length++;
        if (length > maxLength)
          ((maxLength = length),
            (maxOffset = node.offset),
            (mode = BPS_ACTION_SOURCE_COPY));
        node = node.next;
      }
    }

    {
      //target copy
      var node = targetTree[symbol];
      while (node) {
        var length = 0,
          x = node.offset,
          y = outputOffset;
        while (y < targetSize && targetData[x++] == targetData[y++]) length++;
        if (length > maxLength)
          ((maxLength = length),
            (maxOffset = node.offset),
            (mode = BPS_ACTION_TARGET_COPY));
        node = node.next;
      }

      //target tree append
      node = new BPS_Node();
      node.offset = outputOffset;
      node.next = targetTree[symbol];
      targetTree[symbol] = node;
    }

    {
      //target read
      if (maxLength < 4) {
        maxLength = Math.min(Granularity, targetSize - outputOffset);
        mode = BPS_ACTION_TARGET_READ;
      }
    }

    if (mode != BPS_ACTION_TARGET_READ) targetReadFlush();

    switch (mode) {
      case BPS_ACTION_SOURCE_READ:
        //encode(BPS_ACTION_SOURCE_READ | ((maxLength - 1) << 2));
        patchActions.push({ type: BPS_ACTION_SOURCE_READ, length: maxLength });
        break;
      case BPS_ACTION_TARGET_READ:
        //delay write to group sequential TargetRead commands into one
        targetReadLength += maxLength;
        break;
      case BPS_ACTION_SOURCE_COPY:
      case BPS_ACTION_TARGET_COPY:
        //encode(mode | ((maxLength - 1) << 2));
        var relativeOffset;
        if (mode == BPS_ACTION_SOURCE_COPY) {
          relativeOffset = maxOffset - sourceRelativeOffset;
          sourceRelativeOffset = maxOffset + maxLength;
        } else {
          relativeOffset = maxOffset - targetRelativeOffset;
          targetRelativeOffset = maxOffset + maxLength;
        }
        //encode((relativeOffset < 0) | (abs(relativeOffset) << 1));
        patchActions.push({
          type: mode,
          length: maxLength,
          relativeOffset: relativeOffset,
        });
        break;
    }

    outputOffset += maxLength;
  }

  targetReadFlush();

  return patchActions;
}
