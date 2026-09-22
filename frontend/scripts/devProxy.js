/**
 * Vite dev/preview proxy for RomM API, WebSocket, OpenAPI, and library assets.
 * Target comes from DEV_PROXY_TARGET (remote) or local backend on DEV_PORT.
 */

/** @typedef {{ target: string; remote: boolean; warning?: string }} ResolvedDevProxyTarget */

/**
 * @param {string | undefined} raw
 * @param {string} [backendPort]
 * @returns {ResolvedDevProxyTarget}
 */
export function resolveDevProxyTarget(raw, backendPort = "5000") {
  const localTarget = `http://127.0.0.1:${backendPort}`;
  const trimmed = raw?.trim();
  if (!trimmed) {
    return { target: localTarget, remote: false };
  }

  /** @type {URL} */
  let url;
  try {
    url = new URL(trimmed);
  } catch {
    return {
      target: localTarget,
      remote: false,
      warning: `DEV_PROXY_TARGET is not a valid URL ("${trimmed}"); using ${localTarget} instead.`,
    };
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return {
      target: localTarget,
      remote: false,
      warning: `DEV_PROXY_TARGET must be http or https (got "${url.protocol}"); using ${localTarget} instead.`,
    };
  }

  const hostname = url.hostname;
  const isLocal =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "[::1]";

  return { target: url.origin, remote: !isLocal };
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
 * @param {{ remote: boolean }} options
 */
export function createRommDevProxy(target, { remote }) {
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

  // Remote only: local dev serves covers from the frontend/assets symlink.
  if (remote) {
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
  if (resolved.remote) {
    console.log(
      `[vite] DEV_PROXY_TARGET: proxying /api, /ws, /assets/romm to ${resolved.target}`,
    );
  }
}
