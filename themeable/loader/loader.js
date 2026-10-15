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
  function choose() {
    var fromUrl = null;
    try {
      fromUrl = new URLSearchParams(location.search).get("romm-theme");
    } catch (e) {
      fromUrl = null;
    }
    if (fromUrl && known(fromUrl)) {
      save(fromUrl);
      return fromUrl;
    }
    var stored = readStored();
    if (stored && known(stored)) return stored;
    var cookie = readCookie();
    if (cookie && known(cookie)) return cookie;
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

  var current = choose();
  // nginx picks artwork from this cookie, so it must match before any image is requested.
  if (readCookie() !== current) writeCookie(current);
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
