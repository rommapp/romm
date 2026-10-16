/* themeable loader: picks the active theme pack before RomM renders.
 * Classic script injected at the end of <head>; scripts/build.mjs embeds the pack manifest. */
(function () {
  "use strict";
  var manifest = __THEMEABLE_MANIFEST__;
  var STORAGE_KEY = "romm-themeable.theme";
  var COOKIE = "romm_theme";
  var root = document.documentElement;

  function find(id) {
    for (var i = 0; i < manifest.themes.length; i++) {
      if (manifest.themes[i].id === id) return manifest.themes[i];
    }
    return null;
  }
  function known(id) {
    return id === "none" || find(id) !== null;
  }
  function readStored() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }
  function readCookie() {
    var m = document.cookie.match(/(?:^|;\s*)romm_theme=([a-z0-9-]+)/);
    return m ? m[1] : null;
  }
  function writeCookie(id) {
    var secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = COOKIE + "=" + id + "; Path=/; Max-Age=31536000; SameSite=Lax" + secure;
  }
  function save(id) {
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch (e) {
      /* private mode: the cookie still carries the choice */
    }
    writeCookie(id);
  }
  var previewing = false;
  function choose() {
    var fromUrl = null;
    try {
      fromUrl = new URLSearchParams(location.search).get("romm-theme");
    } catch (e) {
      fromUrl = null;
    }
    var preview = null;
    try {
      preview = new URLSearchParams(location.search).get("romm-theme-preview");
    } catch (e) {
      preview = null;
    }
    if (preview && known(preview)) {
      previewing = true;
      return preview;
    }
    if (fromUrl === "default") {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch (e) {
        /* nothing stored to clear */
      }
    } else if (fromUrl && known(fromUrl)) {
      save(fromUrl);
      return fromUrl;
    }
    var stored = readStored();
    if (stored && known(stored)) return stored;
    // The cookie only carries the theme to nginx; the server's choice applies to anyone who hasn't picked one.
    return known(manifest.default) ? manifest.default : "none";
  }

  function apply(id) {
    var theme = find(id);
    root.setAttribute("data-romm-theme", id);
    var old = document.getElementById("themeable-css");
    if (old) old.parentNode.removeChild(old);
    if (theme) {
      var link = document.createElement("link");
      link.id = "themeable-css";
      link.rel = "stylesheet";
      link.href = theme.css;
      link.setAttribute("blocking", "render");
      document.head.appendChild(link);
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      if (!meta.hasAttribute("data-themeable-stock")) {
        meta.setAttribute("data-themeable-stock", meta.getAttribute("content") || "");
      }
      meta.setAttribute(
        "content",
        (theme && theme.themeColor) || meta.getAttribute("data-themeable-stock"),
      );
    }
  }

  // A preview tab names its theme on each artwork URL instead, so the cookie other tabs share stays put.
  var ARTWORK_ATTRS = ["src", "srcset", "href", "xlink:href", "poster", "style"];
  function tagUrl(url) {
    try {
      var u = new URL(url, location.href);
      if (u.origin !== location.origin || u.pathname.indexOf("/assets/") !== 0 || u.searchParams.has(COOKIE)) return url;
      u.searchParams.set(COOKIE, current);
      return u.pathname + u.search + u.hash;
    } catch (e) {
      return url;
    }
  }
  function tagValue(name, value) {
    if (name === "style") {
      return value.replace(/url\((['"]?)([^'")]+)\1\)/g, function (m, q, url) {
        return "url(" + q + tagUrl(url) + q + ")";
      });
    }
    if (name === "srcset") {
      return value
        .split(",")
        .map(function (part) {
          var bits = part.trim().split(/\s+/);
          bits[0] = tagUrl(bits[0]);
          return bits.join(" ");
        })
        .join(", ");
    }
    return tagUrl(value);
  }
  function tagElement(el) {
    if (el.nodeType !== 1) return;
    for (var i = 0; i < ARTWORK_ATTRS.length; i++) {
      var name = ARTWORK_ATTRS[i];
      if (name !== "style" && name !== "poster" && !/^(img|source|image|video)$/i.test(el.tagName)) continue;
      var value = el.getAttribute(name);
      if (!value || value.indexOf("/assets/") < 0) continue;
      var tagged = tagValue(name, value);
      if (tagged !== value) el.setAttribute(name, tagged);
    }
  }
  function tagTree(node) {
    tagElement(node);
    if (node.querySelectorAll) {
      var all = node.querySelectorAll("img, source, image, video, [style*='/assets/']");
      for (var i = 0; i < all.length; i++) tagElement(all[i]);
    }
  }

  var current = choose();
  if (previewing) {
    tagTree(root);
    new MutationObserver(function (records) {
      for (var i = 0; i < records.length; i++) {
        var r = records[i];
        if (r.type === "attributes") tagElement(r.target);
        else for (var j = 0; j < r.addedNodes.length; j++) tagTree(r.addedNodes[j]);
      }
    }).observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ARTWORK_ATTRS });
  } else if (readCookie() !== current) {
    // nginx picks artwork from this cookie, so it must match before any image is requested.
    writeCookie(current);
  }
  apply(current);

  var previewStyle = null;
  window.rommThemeable = {
    manifest: manifest,
    current: function () {
      return current;
    },
    /** Switches theme; reloads so artwork is fetched again under the new cookie. */
    set: function (id) {
      if (!known(id)) throw new Error("Unknown theme: " + id);
      save(id);
      location.reload();
    },
    /** Live CSS preview used by the theme editor; pass null to clear. */
    preview: function (css) {
      if (!previewStyle) {
        previewStyle = document.createElement("style");
        previewStyle.id = "themeable-preview";
        document.head.appendChild(previewStyle);
      }
      previewStyle.textContent = css || "";
    },
  };

  window.addEventListener("message", function (event) {
    if (event.origin !== location.origin) return;
    var data = event.data;
    if (data && data.type === "themeable:preview") window.rommThemeable.preview(data.css);
  });
})();
