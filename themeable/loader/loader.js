/* themeable loader: picks the active theme pack before RomM renders.
 * Classic script injected at the end of <head>; scripts/build.mjs embeds the pack manifest. */
(function () {
  "use strict";
  var manifest = __THEMEABLE_MANIFEST__;
  var client = manifest.client;
  var STOCK = client.stock_id;
  var RANDOM = client.random_id;
  var STORAGE_KEY = client.storage_key;
  var COOKIE = client.cookie;
  var COOKIE_VALUE = new RegExp("(?:^|;\\s*)" + COOKIE + "=([a-z0-9-]+)");
  var root = document.documentElement;

  function find(id) {
    for (var i = 0; i < manifest.themes.length; i++) {
      if (manifest.themes[i].id === id) return manifest.themes[i];
    }
    return null;
  }
  function known(id) {
    return id === STOCK || id === RANDOM || find(id) !== null;
  }
  function readStored() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }
  function readCookie() {
    var m = document.cookie.match(COOKIE_VALUE);
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
    // Random's cookie is written once a pack is drawn, since nginx needs a real pack id.
    if (id !== RANDOM) writeCookie(id);
  }
  var previewing = false;
  function choose() {
    var fromUrl = null;
    try {
      fromUrl = new URLSearchParams(location.search).get(client.url_param);
    } catch (e) {
      fromUrl = null;
    }
    var preview = null;
    try {
      preview = new URLSearchParams(location.search).get(client.preview_param);
    } catch (e) {
      preview = null;
    }
    if (preview && known(preview)) {
      previewing = true;
      return preview;
    }
    if (fromUrl === client.follow_server_id) {
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
    return known(manifest.default) ? manifest.default : STOCK;
  }

  // One draw per page load from the ids the compiler resolved, so artwork and colors match.
  function draw(avoid) {
    var ids = manifest.random ? manifest.random.ids : [];
    var pool = ids.length > 1 ? ids.filter(function (id) {
      return id !== avoid;
    }) : ids;
    if (!pool.length) return STOCK;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function apply(id) {
    var theme = find(id);
    root.setAttribute(client.theme_attribute, id);
    var old = document.getElementById(client.stylesheet_id);
    if (old) old.parentNode.removeChild(old);
    if (theme) {
      var link = document.createElement("link");
      link.id = client.stylesheet_id;
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
  function tagUrl(url, anyPath) {
    try {
      var u = new URL(url, location.href);
      if (u.origin !== location.origin || (!anyPath && u.pathname.indexOf("/assets/") !== 0) || u.searchParams.has(COOKIE)) return url;
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
    // Tab icons sit at the site root; nginx picks a preview's from the same argument.
    if (/^link$/i.test(el.tagName)) {
      var href = el.getAttribute("href");
      var icon = href && /icon/i.test(el.getAttribute("rel") || "") ? tagUrl(href, true) : href;
      if (icon !== href) el.setAttribute("href", icon);
      return;
    }
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
      var all = node.querySelectorAll("img, source, image, video, link[rel*='icon'], [style*='/assets/']");
      for (var i = 0; i < all.length; i++) tagElement(all[i]);
    }
  }

  // The cookie still names the pack this browser showed last, which Random avoids repeating.
  var lastShown = readCookie();
  var current = choose();
  if (current === RANDOM) current = draw(lastShown);
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
