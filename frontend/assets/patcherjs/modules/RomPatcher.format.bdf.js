/* BDF module for Rom Patcher JS v20250922 - Marc Robledo 2025 - http://www.marcrobledo.com/license */
/* File format specification: https://www.daemonology.net/bsdiff/ */

const BDF_MAGIC = "BSDIFF40";

if (typeof module !== "undefined" && module.exports) {
  module.exports = BDF;
}

function BDF() {
  this.records = [];
  this.patchedSize = 0;
}

BDF.prototype.apply = function (file) {
  var tempFile = new BinFile(this.patchedSize);

  for (const record of this.records) {
    for (const b of record.diff) {
      tempFile.writeU8(file.readU8() + b);
    }
    tempFile.writeBytes(record.extra);
    file.seek(file.offset + record.skip);
  }
  return tempFile;
};

BDF.MAGIC = BDF_MAGIC;

BDF.fromFile = function (file) {
  var patch = new BDF();

  file.seek(8);
  file.littleEndian = true;
  var controlSize = file.readU64();
  var diffSize = file.readU64();
  patch.patchedSize = file.readU64();

  var controlCompressed = file.readBytes(controlSize);
  var diffCompressed = file.readBytes(diffSize);
  var extraCompressed = file.readBytes(file.fileSize - file.offset);

  var controlFile = new BinFile(bz2.decompress(controlCompressed));
  controlFile.littleEndian = true;
  var diffFile = new BinFile(bz2.decompress(diffCompressed));
  var extraFile = new BinFile(bz2.decompress(extraCompressed));

  while (!controlFile.isEOF()) {
    var diffLen = controlFile.readU64();
    var extraLen = controlFile.readU64();
    var skip = controlFile.readU64();
    if (skip & (1 << 63)) skip = -(skip & ~(1 << 63));
    var diff = diffFile.readBytes(diffLen);
    var extra = extraFile.readBytes(extraLen);
    patch.records.push({ diff, extra, skip });
  }

  return patch;
};

/*
bz2 (C) 2019-present SheetJS LLC

Copyright 2019 SheetJS LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

*/
("use strict");
const bz2 = (function $() {
  let x = [
      0, 79764919, 159529838, 222504665, 319059676, 398814059, 445009330,
      507990021, 638119352, 583659535, 797628118, 726387553, 890018660,
      835552979, 1015980042, 944750013, 1276238704, 1221641927, 1167319070,
      1095957929, 1595256236, 1540665371, 1452775106, 1381403509, 1780037320,
      1859660671, 1671105958, 1733955601, 2031960084, 2111593891, 1889500026,
      1952343757, 2552477408, 2632100695, 2443283854, 2506133561, 2334638140,
      2414271883, 2191915858, 2254759653, 3190512472, 3135915759, 3081330742,
      3009969537, 2905550212, 2850959411, 2762807018, 2691435357, 3560074640,
      3505614887, 3719321342, 3648080713, 3342211916, 3287746299, 3467911202,
      3396681109, 4063920168, 4143685023, 4223187782, 4286162673, 3779000052,
      3858754371, 3904687514, 3967668269, 881225847, 809987520, 1023691545,
      969234094, 662832811, 591600412, 771767749, 717299826, 311336399,
      374308984, 453813921, 533576470, 25881363, 88864420, 134795389, 214552010,
      2023205639, 2086057648, 1897238633, 1976864222, 1804852699, 1867694188,
      1645340341, 1724971778, 1587496639, 1516133128, 1461550545, 1406951526,
      1302016099, 1230646740, 1142491917, 1087903418, 2896545431, 2825181984,
      2770861561, 2716262478, 3215044683, 3143675388, 3055782693, 3001194130,
      2326604591, 2389456536, 2200899649, 2280525302, 2578013683, 2640855108,
      2418763421, 2498394922, 3769900519, 3832873040, 3912640137, 3992402750,
      4088425275, 4151408268, 4197601365, 4277358050, 3334271071, 3263032808,
      3476998961, 3422541446, 3585640067, 3514407732, 3694837229, 3640369242,
      1762451694, 1842216281, 1619975040, 1682949687, 2047383090, 2127137669,
      1938468188, 2001449195, 1325665622, 1271206113, 1183200824, 1111960463,
      1543535498, 1489069629, 1434599652, 1363369299, 622672798, 568075817,
      748617968, 677256519, 907627842, 853037301, 1067152940, 995781531,
      51762726, 131386257, 177728840, 240578815, 269590778, 349224269,
      429104020, 491947555, 4046411278, 4126034873, 4172115296, 4234965207,
      3794477266, 3874110821, 3953728444, 4016571915, 3609705398, 3555108353,
      3735388376, 3664026991, 3290680682, 3236090077, 3449943556, 3378572211,
      3174993278, 3120533705, 3032266256, 2961025959, 2923101090, 2868635157,
      2813903052, 2742672763, 2604032198, 2683796849, 2461293480, 2524268063,
      2284983834, 2364738477, 2175806836, 2238787779, 1569362073, 1498123566,
      1409854455, 1355396672, 1317987909, 1246755826, 1192025387, 1137557660,
      2072149281, 2135122070, 1912620623, 1992383480, 1753615357, 1816598090,
      1627664531, 1707420964, 295390185, 358241886, 404320391, 483945776,
      43990325, 106832002, 186451547, 266083308, 932423249, 861060070,
      1041341759, 986742920, 613929101, 542559546, 756411363, 701822548,
      3316196985, 3244833742, 3425377559, 3370778784, 3601682597, 3530312978,
      3744426955, 3689838204, 3819031489, 3881883254, 3928223919, 4007849240,
      4037393693, 4100235434, 4180117107, 4259748804, 2310601993, 2373574846,
      2151335527, 2231098320, 2596047829, 2659030626, 2470359227, 2550115596,
      2947551409, 2876312838, 2788305887, 2733848168, 3165939309, 3094707162,
      3040238851, 2985771188,
    ],
    f = [
      0, 1, 3, 7, 15, 31, 63, 127, 255, 511, 1023, 2047, 4095, 8191, 16383,
      32767, 65535, 131071, 262143, 524287, 1048575, 2097151, 4194303, 8388607,
      16777215, 33554431, 67108863, 134217727, 268435455, 536870911, 1073741823,
      -2147483648,
    ];
  function e($) {
    let x = [];
    for (let f = 0; f < $.length; f += 1) x.push([f, $[f]]);
    x.push([$.length, -1]);
    let e = [],
      d = x[0][0],
      b = x[0][1];
    for (let _ = 0; _ < x.length; _ += 1) {
      let a = x[_][0],
        c = x[_][1];
      if (b)
        for (let t = d; t < a; t += 1)
          e.push({ code: t, bits: b, symbol: void 0 });
      if (((d = a), (b = c), -1 === c)) break;
    }
    e.sort(($, x) => $.bits - x.bits || $.code - x.code);
    let l = 0,
      o = -1,
      r = [],
      n;
    for (let s = 0; s < e.length; s += 1) {
      let i = e[s];
      ((o += 1),
        i.bits !== l && ((o <<= i.bits - l), (n = r[(l = i.bits)] = {})),
        (i.symbol = o),
        (n[o] = i));
    }
    return { table: e, fastAccess: r };
  }
  function d($, x) {
    if (x < 0 || x >= $.length) throw RangeError("Out of bound");
    let f = $.slice();
    $.sort(($, x) => $ - x);
    let e = {};
    for (let d = $.length - 1; d >= 0; d -= 1) e[$[d]] = d;
    let b = [];
    for (let _ = 0; _ < $.length; _ += 1) b.push(e[f[_]]++);
    let a,
      c = $[(a = x)],
      t = [];
    for (let l = 1; l < $.length; l += 1) {
      let o = $[(a = b[a])];
      void 0 === o ? t.push(255) : t.push(o);
    }
    return (t.push(c), t.reverse(), t);
  }
  let b = {
    decompress: function $(b, _ = !1) {
      let a = 0,
        c = 0,
        t = 0,
        l = ($) => {
          if ($ >= 32) {
            let x = $ >> 1;
            return l(x) * (1 << x) + l($ - x);
          }
          for (; t < $; ) ((c = (c << 8) + b[a]), (a += 1), (t += 8));
          let e = f[$],
            d = (c >> (t - $)) & e;
          return ((t -= $), (c &= ~(e << t)), d);
        },
        o = l(16);
      if (16986 !== o) throw Error("Invalid magic");
      let r = l(8);
      if (104 !== r) throw Error("Invalid method");
      let n = l(8);
      if (n >= 49 && n <= 57) n -= 48;
      else throw Error("Invalid blocksize");
      let s = new Uint8Array(1.5 * b.length),
        i = 0,
        h = -1;
      for (;;) {
        let u = l(48),
          p = 0 | l(32);
        if (54156738319193 === u) {
          if (l(1)) throw Error("do not support randomised");
          let g = l(24),
            w = [],
            m = l(16);
          for (let v = 32768; v > 0; v >>= 1) {
            if (!(m & v)) {
              for (let y = 0; y < 16; y += 1) w.push(!1);
              continue;
            }
            let k = l(16);
            for (let I = 32768; I > 0; I >>= 1) w.push(!!(k & I));
          }
          let A = l(3);
          if (A < 2 || A > 6) throw Error("Invalid number of huffman groups");
          let z = l(15),
            C = [],
            O = Array.from({ length: A }, ($, x) => x);
          for (let F = 0; F < z; F += 1) {
            let H = 0;
            for (; l(1); )
              if ((H += 1) >= A) throw Error("MTF table out of range");
            let M = O[H];
            for (let P = H; P > 0; O[P] = O[--P]);
            (C.push(M), (O[0] = M));
          }
          let R = w.reduce(($, x) => $ + x, 0) + 2,
            T = [];
          for (let j = 0; j < A; j += 1) {
            let q = l(5),
              B = [];
            for (let D = 0; D < R; D += 1) {
              if (q < 0 || q > 20)
                throw Error("Huffman group length outside range");
              for (; l(1); ) q -= 2 * l(1) - 1;
              B.push(q);
            }
            T.push(e(B));
          }
          let E = [];
          for (let G = 0; G < w.length - 1; G += 1) w[G] && E.push(G);
          let J = 0,
            K = 0,
            L,
            N,
            Q = 0,
            S = 0,
            U = [];
          for (;;) {
            for (let V in ((J -= 1) <= 0 &&
              ((J = 50), K <= C.length && ((L = T[C[K]]), (K += 1))),
            L.fastAccess))
              if (
                Object.prototype.hasOwnProperty.call(L.fastAccess, V) &&
                (t < V && ((c = (c << 8) + b[a]), (a += 1), (t += 8)),
                (N = L.fastAccess[V][c >> (t - V)]))
              ) {
                ((c &= f[(t -= V)]), (N = N.code));
                break;
              }
            if (N >= 0 && N <= 1) {
              (0 === Q && (S = 1), (Q += S << N), (S <<= 1));
              continue;
            }
            {
              let W = E[0];
              for (; Q > 0; Q -= 1) U.push(W);
            }
            if (N === R - 1) break;
            {
              let X = E[N - 1];
              for (let Y = N - 1; Y > 0; E[Y] = E[--Y]);
              ((E[0] = X), U.push(X));
            }
          }
          let Z = d(U, g),
            $$ = 0;
          for (; $$ < Z.length; ) {
            let $x = Z[$$],
              $f = 1;
            if (
              ($$ < Z.length - 4 &&
              Z[$$ + 1] === $x &&
              Z[$$ + 2] === $x &&
              Z[$$ + 3] === $x
                ? (($f = Z[$$ + 4] + 4), ($$ += 5))
                : ($$ += 1),
              i + $f >= s.length)
            ) {
              let $e = s;
              (s = new Uint8Array(2 * $e.length)).set($e);
            }
            for (let $d = 0; $d < $f; $d += 1)
              (_ && (h = (h << 8) ^ x[((h >> 24) ^ $x) & 255]),
                (s[i] = $x),
                (i += 1));
          }
          if (_) {
            let $b = -1 ^ h;
            if ($b !== p) throw Error(`CRC mismatch: ${$b} !== ${p}`);
            h = -1;
          }
        } else if (25779555029136 === u) {
          l(7 & t);
          break;
        } else throw Error("Invalid bz2 blocktype");
      }
      return s.subarray(0, i);
    },
  };
  return b;
})();
