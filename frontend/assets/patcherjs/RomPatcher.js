/*
 * Rom Patcher JS core
 * A ROM patcher/builder made in JavaScript, can be implemented as a webapp or a Node.JS CLI tool
 * By Marc Robledo https://www.marcrobledo.com
 * Sourcecode: https://github.com/marcrobledo/RomPatcher.js
 * License:
 *
 * MIT License
 *
 * Copyright (c) 2016-2025 Marc Robledo
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

const RomPatcher = (function () {
  const TOO_BIG_ROM_SIZE = 67108863;

  const HEADERS_INFO = [
    {
      extensions: ["nes"],
      size: 16,
      romSizeMultiple: 1024,
      name: "iNES",
    } /* https://www.nesdev.org/wiki/INES */,
    {
      extensions: ["fds"],
      size: 16,
      romSizeMultiple: 65500,
      name: "fwNES",
    } /* https://www.nesdev.org/wiki/FDS_file_format */,
    { extensions: ["lnx"], size: 64, romSizeMultiple: 1024, name: "LNX" },
    {
      extensions: ["sfc", "smc", "swc", "fig"],
      size: 512,
      romSizeMultiple: 262144,
      name: "SNES copier",
    },
  ];

  const GAME_BOY_NINTENDO_LOGO = [
    0xce, 0xed, 0x66, 0x66, 0xcc, 0x0d, 0x00, 0x0b, 0x03, 0x73, 0x00, 0x83,
    0x00, 0x0c, 0x00, 0x0d, 0x00, 0x08, 0x11, 0x1f, 0x88, 0x89, 0x00, 0x0e,
    0xdc, 0xcc, 0x6e, 0xe6, 0xdd, 0xdd, 0xd9, 0x99,
  ];

  const _getRomSystem = function (binFile) {
    /* to-do: add more systems */
    const extension = binFile.getExtension().trim();
    if (binFile.fileSize > 0x0200 && binFile.fileSize % 4 === 0) {
      if (
        (extension === "gb" || extension === "gbc") &&
        binFile.fileSize % 0x4000 === 0
      ) {
        binFile.seek(0x0104);
        var valid = true;
        for (var i = 0; i < GAME_BOY_NINTENDO_LOGO.length && valid; i++) {
          if (GAME_BOY_NINTENDO_LOGO[i] !== binFile.readU8()) valid = false;
        }
        if (valid) return "gb";
      } else if (extension === "md" || extension === "bin") {
        binFile.seek(0x0100);
        if (/SEGA (GENESIS|MEGA DR)/.test(binFile.readString(12))) return "smd";
      } else if (extension === "z64" && binFile.fileSize >= 0x400000) {
        return "n64";
      }
    } else if (extension === "fds" && binFile.fileSize % 65500 === 0) {
      return "fds";
    }
    return null;
  };
  const _getRomAdditionalChecksum = function (binFile) {
    /* to-do: add more systems */
    const romSystem = _getRomSystem(binFile);
    if (romSystem === "n64") {
      binFile.seek(0x3c);
      const cartId = binFile.readString(3);

      binFile.seek(0x10);
      const crc = binFile.readBytes(8).reduce(function (hex, b) {
        if (b < 16) return hex + "0" + b.toString(16);
        else return hex + b.toString(16);
      }, "");
      return cartId + " (" + crc + ")";
    }
    return null;
  };

  return {
    parsePatchFile: function (patchFile) {
      if (!(patchFile instanceof BinFile))
        throw new Error("Patch file is not an instance of BinFile");

      patchFile.littleEndian = false;
      patchFile.seek(0);

      var header = patchFile.readString(8);
      var patch = null;
      if (header.startsWith(IPS.MAGIC)) {
        patch = IPS.fromFile(patchFile);
      } else if (header.startsWith(UPS.MAGIC)) {
        patch = UPS.fromFile(patchFile);
      } else if (header.startsWith(APS.MAGIC)) {
        patch = APS.fromFile(patchFile);
      } else if (header.startsWith(APSGBA.MAGIC)) {
        patch = APSGBA.fromFile(patchFile);
      } else if (header.startsWith(BPS.MAGIC)) {
        patch = BPS.fromFile(patchFile);
      } else if (header.startsWith(RUP.MAGIC)) {
        patch = RUP.fromFile(patchFile);
      } else if (header.startsWith(PPF.MAGIC)) {
        patch = PPF.fromFile(patchFile);
      } else if (header.startsWith(BDF.MAGIC)) {
        patch = BDF.fromFile(patchFile);
      } else if (header.startsWith(PMSR.MAGIC)) {
        patch = PMSR.fromFile(patchFile);
      } else if (header.startsWith(VCDIFF.MAGIC)) {
        patch = VCDIFF.fromFile(patchFile);
      }

      if (patch) patch._originalPatchFile = patchFile;

      return patch;
    },

    validateRom: function (romFile, patch, skipHeaderSize) {
      if (!(romFile instanceof BinFile))
        throw new Error("ROM file is not an instance of BinFile");
      else if (typeof patch !== "object")
        throw new Error("Unknown patch format");

      if (typeof skipHeaderSize !== "number" || skipHeaderSize < 0)
        skipHeaderSize = 0;

      if (
        typeof patch.validateSource === "function" &&
        !patch.validateSource(romFile, skipHeaderSize)
      ) {
        return false;
      }
      return true;
    },

    applyPatch: function (romFile, patch, optionsParam) {
      if (!(romFile instanceof BinFile))
        throw new Error("ROM file is not an instance of BinFile");
      else if (typeof patch !== "object")
        throw new Error("Unknown patch format");

      const options = {
        requireValidation: false,
        removeHeader: false,
        addHeader: false,
        fixChecksum: false,
        outputSuffix: true,
      };
      if (typeof optionsParam === "object") {
        if (typeof optionsParam.requireValidation !== "undefined")
          options.requireValidation = !!optionsParam.requireValidation;
        if (typeof optionsParam.removeHeader !== "undefined")
          options.removeHeader = !!optionsParam.removeHeader;
        if (typeof optionsParam.addHeader !== "undefined")
          options.addHeader = !!optionsParam.addHeader;
        if (typeof optionsParam.fixChecksum !== "undefined")
          options.fixChecksum = !!optionsParam.fixChecksum;
        if (typeof optionsParam.outputSuffix !== "undefined")
          options.outputSuffix = !!optionsParam.outputSuffix;
      }

      var extractedHeader = false;
      var fakeHeaderSize = 0;
      if (options.removeHeader) {
        const headerInfo = RomPatcher.isRomHeadered(romFile);
        if (headerInfo) {
          const splitData = RomPatcher.removeHeader(romFile);
          extractedHeader = splitData.header;
          romFile = splitData.rom;
        }
      } else if (options.addHeader) {
        const headerInfo = RomPatcher.canRomGetHeader(romFile);
        if (headerInfo) {
          fakeHeaderSize = headerInfo.fileSize;
          romFile = RomPatcher.addFakeHeader(romFile);
        }
      }

      if (
        options.requireValidation &&
        !RomPatcher.validateRom(romFile, patch)
      ) {
        throw new Error("Invalid input ROM checksum");
      }

      var patchedRom = patch.apply(romFile);
      if (extractedHeader) {
        /* reinsert header */
        if (options.fixChecksum) RomPatcher.fixRomHeaderChecksum(patchedRom);

        const patchedRomWithHeader = new BinFile(
          extractedHeader.fileSize + patchedRom.fileSize,
        );
        patchedRomWithHeader.fileName = patchedRom.fileName;
        patchedRomWithHeader.fileType = patchedRom.fileType;
        extractedHeader.copyTo(
          patchedRomWithHeader,
          0,
          extractedHeader.fileSize,
        );
        patchedRom.copyTo(
          patchedRomWithHeader,
          0,
          patchedRom.fileSize,
          extractedHeader.fileSize,
        );

        patchedRom = patchedRomWithHeader;
      } else if (fakeHeaderSize) {
        /* remove fake header */
        const patchedRomWithoutFakeHeader = patchedRom.slice(fakeHeaderSize);

        if (options.fixChecksum)
          RomPatcher.fixRomHeaderChecksum(patchedRomWithoutFakeHeader);

        patchedRom = patchedRomWithoutFakeHeader;
      } else if (options.fixChecksum) {
        RomPatcher.fixRomHeaderChecksum(patchedRom);
      }

      if (options.outputSuffix) {
        patchedRom.fileName = romFile.fileName.replace(
          /\.([^\.]*?)$/,
          " (patched).$1",
        );
        if (patchedRom.unpatched)
          patchedRom.fileName = patchedRom.fileName.replace(
            " (patched)",
            " (unpatched)",
          );
      } else if (patch._originalPatchFile) {
        patchedRom.fileName = patch._originalPatchFile.fileName.replace(
          /\.\w+$/i,
          /\.\w+$/i.test(romFile.fileName)
            ? romFile.fileName.match(/\.\w+$/i)[0]
            : "",
        );
      } else {
        patchedRom.fileName = romFile.fileName;
      }

      return patchedRom;
    },

    createPatch: function (originalFile, modifiedFile, format, metadata) {
      if (!(originalFile instanceof BinFile))
        throw new Error("Original ROM file is not an instance of BinFile");
      else if (!(modifiedFile instanceof BinFile))
        throw new Error("Modified ROM file is not an instance of BinFile");

      if (typeof format === "string") format = format.trim().toLowerCase();
      else if (typeof format === "undefined") format = "ips";

      var patch;
      if (format === "ips") {
        patch = IPS.buildFromRoms(originalFile, modifiedFile);
      } else if (format === "bps") {
        patch = BPS.buildFromRoms(
          originalFile,
          modifiedFile,
          originalFile.fileSize <= 4194304,
        );
      } else if (format === "ppf") {
        patch = PPF.buildFromRoms(originalFile, modifiedFile);
      } else if (format === "ups") {
        patch = UPS.buildFromRoms(originalFile, modifiedFile);
      } else if (format === "aps") {
        patch = APS.buildFromRoms(originalFile, modifiedFile);
      } else if (format === "rup") {
        patch = RUP.buildFromRoms(
          originalFile,
          modifiedFile,
          metadata && metadata.Description ? metadata.Description : null,
        );
      } else if (format === "ebp") {
        patch = IPS.buildFromRoms(originalFile, modifiedFile, metadata);
      } else {
        throw new Error("Invalid patch format");
      }

      if (
        !(format === "ppf" && originalFile.fileSize > modifiedFile.fileSize) && //skip verification if PPF and PPF+modified size>original size
        modifiedFile.hashCRC32() !== patch.apply(originalFile).hashCRC32()
      ) {
        //throw new Error('Unexpected error: verification failed. Patched file and modified file mismatch. Please report this bug.');
      }
      return patch;
    },

    /* check if ROM can inject a fake header (for patches that require a headered ROM) */
    canRomGetHeader: function (romFile) {
      if (romFile.fileSize <= 0x600000) {
        const compatibleHeader = HEADERS_INFO.find(
          (headerInfo) =>
            headerInfo.extensions.indexOf(romFile.getExtension()) !== -1 &&
            romFile.fileSize % headerInfo.romSizeMultiple === 0,
        );
        if (compatibleHeader) {
          return {
            name: compatibleHeader.name,
            size: compatibleHeader.size,
          };
        }
      }
      return null;
    },

    /* check if ROM has a known header */
    isRomHeadered: function (romFile) {
      if (romFile.fileSize <= 0x600200 && romFile.fileSize % 1024 !== 0) {
        const compatibleHeader = HEADERS_INFO.find(
          (headerInfo) =>
            headerInfo.extensions.indexOf(romFile.getExtension()) !== -1 &&
            (romFile.fileSize - headerInfo.size) %
              headerInfo.romSizeMultiple ===
              0,
        );
        if (compatibleHeader) {
          return {
            name: compatibleHeader.name,
            size: compatibleHeader.size,
          };
        }
      }
      return null;
    },

    /* remove ROM header */
    removeHeader: function (romFile) {
      const headerInfo = RomPatcher.isRomHeadered(romFile);
      if (headerInfo) {
        return {
          header: romFile.slice(0, headerInfo.size),
          rom: romFile.slice(headerInfo.size),
        };
      }
      return null;
    },

    /* add fake ROM header */
    addFakeHeader: function (romFile) {
      const headerInfo = RomPatcher.canRomGetHeader(romFile);
      if (headerInfo) {
        const romWithFakeHeader = new BinFile(
          headerInfo.size + romFile.fileSize,
        );
        romWithFakeHeader.fileName = romFile.fileName;
        romWithFakeHeader.fileType = romFile.fileType;
        romFile.copyTo(romWithFakeHeader, 0, romFile.fileSize, headerInfo.size);

        //add a correct FDS header
        if (_getRomSystem(romWithFakeHeader) === "fds") {
          romWithFakeHeader.seek(0);
          romWithFakeHeader.writeBytes([
            0x46,
            0x44,
            0x53,
            0x1a,
            romFile.fileSize / 65500,
          ]);
        }

        romWithFakeHeader.fakeHeader = true;

        return romWithFakeHeader;
      }
      return null;
    },

    /* get ROM internal checksum, if possible */
    fixRomHeaderChecksum: function (romFile) {
      const romSystem = _getRomSystem(romFile);

      if (romSystem === "gb") {
        /* get current checksum */
        romFile.seek(0x014d);
        const currentChecksum = romFile.readU8();

        /* calculate checksum */
        var newChecksum = 0x00;
        romFile.seek(0x0134);
        for (var i = 0; i <= 0x18; i++) {
          newChecksum = ((newChecksum - romFile.readU8() - 1) >>> 0) & 0xff;
        }

        /* fix checksum */
        if (currentChecksum !== newChecksum) {
          console.log("fixed Game Boy checksum");
          romFile.seek(0x014d);
          romFile.writeU8(newChecksum);
          return true;
        }
      } else if (romSystem === "smd") {
        /* get current checksum */
        romFile.seek(0x018e);
        const currentChecksum = romFile.readU16();

        /* calculate checksum */
        var newChecksum = 0x0000;
        romFile.seek(0x0200);
        while (!romFile.isEOF()) {
          newChecksum = ((newChecksum + romFile.readU16()) >>> 0) & 0xffff;
        }

        /* fix checksum */
        if (currentChecksum !== newChecksum) {
          console.log("fixed Megadrive/Genesis checksum");
          romFile.seek(0x018e);
          romFile.writeU16(newChecksum);
          return true;
        }
      }

      return false;
    },

    /* get ROM additional checksum info, if possible */
    getRomAdditionalChecksum: function (romFile) {
      return _getRomAdditionalChecksum(romFile);
    },

    /* check if ROM is too big */
    isRomTooBig: function (romFile) {
      return romFile && romFile.fileSize > TOO_BIG_ROM_SIZE;
    },
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = RomPatcher;

  IPS = require("./modules/RomPatcher.format.ips");
  UPS = require("./modules/RomPatcher.format.ups");
  APS = require("./modules/RomPatcher.format.aps_n64");
  APSGBA = require("./modules/RomPatcher.format.aps_gba");
  BPS = require("./modules/RomPatcher.format.bps");
  RUP = require("./modules/RomPatcher.format.rup");
  PPF = require("./modules/RomPatcher.format.ppf");
  BDF = require("./modules/RomPatcher.format.bdf");
  PMSR = require("./modules/RomPatcher.format.pmsr");
  VCDIFF = require("./modules/RomPatcher.format.vcdiff");
}
