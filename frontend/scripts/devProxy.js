/**
 * Vite dev/preview proxy for RomM API, WebSocket, OpenAPI, and library assets.
 * Target comes from DEV_PROXY_TARGET (remote) or local backend on DEV_PORT.
 */

/** @typedef {{ target: string; remote: boolean; proxyAssets: boolean; warning?: string }} ResolvedDevProxyTarget */

/**
 * @param {string | undefined} raw
 * @param {string} [backendPort]
 * @returns {ResolvedDevProxyTarget}
 */
export function resolveDevProxyTarget(raw, backendPort = "5000") {
  const localTarget = `http://127.0.0.1:${backendPort}`;
  const trimmed = raw?.trim();
  if (!trimmed) {
    return { target: localTarget, remote: false, proxyAssets: false };
  }

  /** @type {URL} */
  let url;
  try {
    url = new URL(trimmed);
  } catch {
    return {
      target: localTarget,
      remote: false,
      proxyAssets: false,
      warning: `DEV_PROXY_TARGET is not a valid URL ("${trimmed}"); using ${localTarget} instead.`,
    };
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return {
      target: localTarget,
      remote: false,
      proxyAssets: false,
      warning: `DEV_PROXY_TARGET must be http or https (got "${url.protocol}"); using ${localTarget} instead.`,
    };
  }

  const hostname = url.hostname;
  const isLocal =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "[::1]";

  return { target: url.origin, remote: !isLocal, proxyAssets: true };
}

/** @param {import("http").IncomingMessage} proxyRes */
function rewriteSetCookieForLocalhost(proxyRes) {
  const cookies = proxyRes.headers["set-cookie"];
  if (!cookies) return;
  proxyRes.headers["set-cookie"] = cookies.map((cookie) =>
    cookie.replace(/;\s*Secure/gi, "").replace(/;\s*Domain=[^;]*/gi, ""),
  );
}

/**
 * @param {string} target
 * @param {{ remote: boolean; proxyAssets: boolean }} options
 */
export function createRommDevProxy(target, { remote, proxyAssets }) {
  const shared = remote
    ? {
        changeOrigin: true,
        secure: true,
        configure: (proxy) => {
          proxy.on("proxyRes", rewriteSetCookieForLocalhost);
        },
      }
    : {
        changeOrigin: false,
        secure: false,
      };

  const proxy = {
    "/api": { target, ...shared },
    "^/(?:ws|netplay)": { target, ...shared, ws: true },
    "/openapi.json": {
      target,
      ...shared,
      rewrite: (path) => path.replace(/^\/openapi.json/, "/openapi.json"),
    },
  };

  // Default dev (no DEV_PROXY_TARGET) serves covers from the frontend/assets symlink.
  if (proxyAssets) {
    proxy["/assets/romm"] = { target, ...shared };
  }

  return proxy;
}

/** @param {ResolvedDevProxyTarget} resolved */
export function logDevProxyTarget(resolved) {
  if (resolved.warning) {
    console.warn(`[vite] ${resolved.warning}`);
    return;
  }
  if (resolved.proxyAssets) {
    console.log(
      `[vite] DEV_PROXY_TARGET: proxying /api, /ws, /assets/romm to ${resolved.target}`,
    );
  }
}
