/*
 * HashCalculator.js (last update: 2021-08-15)
 * by Marc Robledo, https://www.marcrobledo.com
 *
 * data hash calculator (CRC32, MD5, SHA1, ADLER-32, CRC16)
 *
 * MIT License
 *
 * Copyright (c) 2016-2021 Marc Robledo
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

const HashCalculator = (function () {
  const HEX_CHR = "0123456789abcdef".split("");

  /* MD5 helpers */
  const _add32 = function (a, b) {
    return (a + b) & 0xffffffff;
  };
  const _md5cycle = function (x, k) {
    var a = x[0],
      b = x[1],
      c = x[2],
      d = x[3];
    a = ff(a, b, c, d, k[0], 7, -680876936);
    d = ff(d, a, b, c, k[1], 12, -389564586);
    c = ff(c, d, a, b, k[2], 17, 606105819);
    b = ff(b, c, d, a, k[3], 22, -1044525330);
    a = ff(a, b, c, d, k[4], 7, -176418897);
    d = ff(d, a, b, c, k[5], 12, 1200080426);
    c = ff(c, d, a, b, k[6], 17, -1473231341);
    b = ff(b, c, d, a, k[7], 22, -45705983);
    a = ff(a, b, c, d, k[8], 7, 1770035416);
    d = ff(d, a, b, c, k[9], 12, -1958414417);
    c = ff(c, d, a, b, k[10], 17, -42063);
    b = ff(b, c, d, a, k[11], 22, -1990404162);
    a = ff(a, b, c, d, k[12], 7, 1804603682);
    d = ff(d, a, b, c, k[13], 12, -40341101);
    c = ff(c, d, a, b, k[14], 17, -1502002290);
    b = ff(b, c, d, a, k[15], 22, 1236535329);
    a = gg(a, b, c, d, k[1], 5, -165796510);
    d = gg(d, a, b, c, k[6], 9, -1069501632);
    c = gg(c, d, a, b, k[11], 14, 643717713);
    b = gg(b, c, d, a, k[0], 20, -373897302);
    a = gg(a, b, c, d, k[5], 5, -701558691);
    d = gg(d, a, b, c, k[10], 9, 38016083);
    c = gg(c, d, a, b, k[15], 14, -660478335);
    b = gg(b, c, d, a, k[4], 20, -405537848);
    a = gg(a, b, c, d, k[9], 5, 568446438);
    d = gg(d, a, b, c, k[14], 9, -1019803690);
    c = gg(c, d, a, b, k[3], 14, -187363961);
    b = gg(b, c, d, a, k[8], 20, 1163531501);
    a = gg(a, b, c, d, k[13], 5, -1444681467);
    d = gg(d, a, b, c, k[2], 9, -51403784);
    c = gg(c, d, a, b, k[7], 14, 1735328473);
    b = gg(b, c, d, a, k[12], 20, -1926607734);
    a = hh(a, b, c, d, k[5], 4, -378558);
    d = hh(d, a, b, c, k[8], 11, -2022574463);
    c = hh(c, d, a, b, k[11], 16, 1839030562);
    b = hh(b, c, d, a, k[14], 23, -35309556);
    a = hh(a, b, c, d, k[1], 4, -1530992060);
    d = hh(d, a, b, c, k[4], 11, 1272893353);
    c = hh(c, d, a, b, k[7], 16, -155497632);
    b = hh(b, c, d, a, k[10], 23, -1094730640);
    a = hh(a, b, c, d, k[13], 4, 681279174);
    d = hh(d, a, b, c, k[0], 11, -358537222);
    c = hh(c, d, a, b, k[3], 16, -722521979);
    b = hh(b, c, d, a, k[6], 23, 76029189);
    a = hh(a, b, c, d, k[9], 4, -640364487);
    d = hh(d, a, b, c, k[12], 11, -421815835);
    c = hh(c, d, a, b, k[15], 16, 530742520);
    b = hh(b, c, d, a, k[2], 23, -995338651);
    a = ii(a, b, c, d, k[0], 6, -198630844);
    d = ii(d, a, b, c, k[7], 10, 1126891415);
    c = ii(c, d, a, b, k[14], 15, -1416354905);
    b = ii(b, c, d, a, k[5], 21, -57434055);
    a = ii(a, b, c, d, k[12], 6, 1700485571);
    d = ii(d, a, b, c, k[3], 10, -1894986606);
    c = ii(c, d, a, b, k[10], 15, -1051523);
    b = ii(b, c, d, a, k[1], 21, -2054922799);
    a = ii(a, b, c, d, k[8], 6, 1873313359);
    d = ii(d, a, b, c, k[15], 10, -30611744);
    c = ii(c, d, a, b, k[6], 15, -1560198380);
    b = ii(b, c, d, a, k[13], 21, 1309151649);
    a = ii(a, b, c, d, k[4], 6, -145523070);
    d = ii(d, a, b, c, k[11], 10, -1120210379);
    c = ii(c, d, a, b, k[2], 15, 718787259);
    b = ii(b, c, d, a, k[9], 21, -343485551);
    x[0] = _add32(a, x[0]);
    x[1] = _add32(b, x[1]);
    x[2] = _add32(c, x[2]);
    x[3] = _add32(d, x[3]);
  };
  const _md5blk = function (d) {
    var md5blks = [],
      i;
    for (i = 0; i < 64; i += 4)
      md5blks[i >> 2] =
        d[i] + (d[i + 1] << 8) + (d[i + 2] << 16) + (d[i + 3] << 24);
    return md5blks;
  };
  const _cmn = function (q, a, b, x, s, t) {
    a = _add32(_add32(a, q), _add32(x, t));
    return _add32((a << s) | (a >>> (32 - s)), b);
  };
  const ff = function (a, b, c, d, x, s, t) {
    return _cmn((b & c) | (~b & d), a, b, x, s, t);
  };
  const gg = function (a, b, c, d, x, s, t) {
    return _cmn((b & d) | (c & ~d), a, b, x, s, t);
  };
  const hh = function (a, b, c, d, x, s, t) {
    return _cmn(b ^ c ^ d, a, b, x, s, t);
  };
  const ii = function (a, b, c, d, x, s, t) {
    return _cmn(c ^ (b | ~d), a, b, x, s, t);
  };

  /* CRC32 helpers */
  const CRC32_TABLE = (function () {
    var c,
      crcTable = [];
    for (var n = 0; n < 256; n++) {
      c = n;
      for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      crcTable[n] = c;
    }
    return crcTable;
  })();

  /* Adler-32 helpers */
  const ADLER32_MOD = 0xfff1;

  const generateUint8Array = function (arrayBuffer, offset, len) {
    if (typeof offset !== "number" || offset < 0) offset = 0;
    else if (offset < arrayBuffer.byteLength) offset = Math.floor(offset);
    else throw new Error("out of bounds slicing");

    if (
      typeof len !== "number" ||
      len < 0 ||
      offset + len >= arrayBuffer.byteLength.length
    )
      len = arrayBuffer.byteLength - offset;
    else if (len > 0) len = Math.floor(len);
    else throw new Error("zero length provided for slicing");

    return new Uint8Array(arrayBuffer, offset, len);
  };

  return {
    /* SHA-1 using WebCryptoAPI */
    sha1: async function sha1(arrayBuffer, offset, len) {
      if (typeof window === "undefined" || typeof window.crypto === "undefined")
        throw new Error("Web Crypto API is not available");

      const u8array = generateUint8Array(arrayBuffer, offset, len);
      if (u8array.byteLength !== arrayBuffer.byteLength) {
        arrayBuffer = arrayBuffer.slice(
          u8array.byteOffset,
          u8array.byteOffset + u8array.byteLength,
        );
      }

      const hash = await window.crypto.subtle.digest("SHA-1", arrayBuffer);

      const bytes = new Uint8Array(hash);
      let hexString = "";
      for (let i = 0; i < bytes.length; i++)
        hexString +=
          bytes[i] < 16 ? "0" + bytes[i].toString(16) : bytes[i].toString(16);
      return hexString;
    },

    /* MD5 - from Joseph's Myers - http://www.myersdaily.org/joseph/javascript/md5.js */
    md5: function (arrayBuffer, offset, len) {
      let u8array = generateUint8Array(arrayBuffer, offset, len);

      var n = u8array.byteLength,
        state = [1732584193, -271733879, -1732584194, 271733878],
        i;
      for (i = 64; i <= u8array.byteLength; i += 64)
        _md5cycle(state, _md5blk(u8array.slice(i - 64, i)));
      u8array = u8array.slice(i - 64);
      var tail = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
      for (i = 0; i < u8array.byteLength; i++)
        tail[i >> 2] |= u8array[i] << ((i % 4) << 3);
      tail[i >> 2] |= 0x80 << ((i % 4) << 3);
      if (i > 55) {
        _md5cycle(state, tail);
        for (i = 0; i < 16; i++) tail[i] = 0;
      }
      tail[14] = n * 8;
      tail[15] = Math.floor(n / 536870912) >>> 0; //if file is bigger than 512Mb*8, value is bigger than 32 bits, so it needs two words to store its length
      _md5cycle(state, tail);

      for (var i = 0; i < state.length; i++) {
        var s = "",
          j = 0;
        for (; j < 4; j++)
          s +=
            HEX_CHR[(state[i] >> (j * 8 + 4)) & 0x0f] +
            HEX_CHR[(state[i] >> (j * 8)) & 0x0f];
        state[i] = s;
      }
      return state.join("");
    },

    /* CRC32 - from Alex - https://stackoverflow.com/a/18639999 */
    crc32: function (arrayBuffer, offset, len) {
      const u8array = generateUint8Array(arrayBuffer, offset, len);

      var crc = 0 ^ -1;

      for (var i = 0; i < u8array.byteLength; i++)
        crc = (crc >>> 8) ^ CRC32_TABLE[(crc ^ u8array[i]) & 0xff];

      return (crc ^ -1) >>> 0;
    },

    /* Adler-32 - https://en.wikipedia.org/wiki/Adler-32#Example_implementation */
    adler32: function (arrayBuffer, offset, len) {
      const u8array = generateUint8Array(arrayBuffer, offset, len);

      var a = 1,
        b = 0;

      for (var i = 0; i < u8array.byteLength; i++) {
        a = (a + u8array[i]) % ADLER32_MOD;
        b = (b + a) % ADLER32_MOD;
      }

      return ((b << 16) | a) >>> 0;
    },

    /* CRC16/CCITT-FALSE */
    crc16: function (arrayBuffer, offset, len) {
      const u8array = generateUint8Array(arrayBuffer, offset, len);

      var crc = 0xffff;

      var offset = 0;

      for (var i = 0; i < u8array.byteLength; i++) {
        crc ^= u8array[offset++] << 8;
        for (j = 0; j < 8; ++j) {
          crc = (crc & 0x8000) >>> 0 ? (crc << 1) ^ 0x1021 : crc << 1;
        }
      }

      return crc & 0xffff;
    },
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HashCalculator;
}
