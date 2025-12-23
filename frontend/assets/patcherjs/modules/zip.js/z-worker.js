/* jshint worker:true */
!(function (c) {
  "use strict";
  if (c.zWorkerInitialized)
    throw new Error("z-worker.js should be run only once");
  ((c.zWorkerInitialized = !0),
    addEventListener("message", function (t) {
      var e,
        r,
        c = t.data,
        n = c.type,
        s = c.sn,
        p = o[n];
      if (p)
        try {
          p(c);
        } catch (t) {
          ((e = {
            type: n,
            sn: s,
            error: ((r = t), { message: r.message, stack: r.stack }),
          }),
            postMessage(e));
        }
    }));
  var o = {
      importScripts: function (t) {
        t.scripts &&
          0 < t.scripts.length &&
          importScripts.apply(void 0, t.scripts);
        postMessage({ type: "importScripts" });
      },
      newTask: h,
      append: t,
      flush: t,
    },
    f = {};
  function h(t) {
    if (typeof c[t.codecClass] !== 'function') {
      throw new Error("Invalid codecClass");
    }
    var e = c[t.codecClass],
      r = t.sn;
    if (f[r]) throw Error("duplicated sn");
    ((f[r] = {
      codec: new e(t.options),
      crcInput: "input" === t.crcType,
      crcOutput: "output" === t.crcType,
      crc: new n(),
    }),
      postMessage({ type: "newTask", sn: r }));
  }
  var l = c.performance ? c.performance.now.bind(c.performance) : Date.now;
  function t(t) {
    var e = t.sn,
      r = t.type,
      c = t.data,
      n = f[e];
    !n && t.codecClass && (h(t), (n = f[e]));
    var s,
      p = "append" === r,
      o = l();
    if (p)
      try {
        s = n.codec.append(c, function (t) {
          postMessage({ type: "progress", sn: e, loaded: t });
        });
      } catch (t) {
        throw (delete f[e], t);
      }
    else (delete f[e], (s = n.codec.flush()));
    var a = l() - o;
    ((o = l()),
      c && n.crcInput && n.crc.append(c),
      s && n.crcOutput && n.crc.append(s));
    var i = l() - o,
      u = { type: r, sn: e, codecTime: a, crcTime: i },
      d = [];
    (s && ((u.data = s), d.push(s.buffer)),
      p || (!n.crcInput && !n.crcOutput) || (u.crc = n.crc.get()));
    try {
      postMessage(u, d);
    } catch (t) {
      postMessage(u);
    }
  }
  function n() {
    this.crc = -1;
  }
  function e() {}
  ((n.prototype.append = function (t) {
    for (
      var e = 0 | this.crc, r = this.table, c = 0, n = 0 | t.length;
      c < n;
      c++
    )
      e = (e >>> 8) ^ r[255 & (e ^ t[c])];
    this.crc = e;
  }),
    (n.prototype.get = function () {
      return ~this.crc;
    }),
    (n.prototype.table = (function () {
      var t,
        e,
        r,
        c = [];
      for (t = 0; t < 256; t++) {
        for (r = t, e = 0; e < 8; e++)
          1 & r ? (r = (r >>> 1) ^ 3988292384) : (r >>>= 1);
        c[t] = r;
      }
      return c;
    })()),
    ((c.NOOP = e).prototype.append = function (t, e) {
      return t;
    }),
    (e.prototype.flush = function () {}));
})(this);
