import { isAxiosError } from "axios";
import Bowser from "bowser";
import syncApi from "@/services/api/sync";
import { randomToken } from "@/services/pending-asset";

// One id per browser profile, sent as the device's hostname so registering
// again finds the same device instead of adding one.
const BROWSER_ID_KEY = "romm:browser-id";
const DEVICE_KEY_PREFIX = "romm:browser-device:";

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Without storage the browser registers again next time, and finds itself.
  }
}

function browserId(): string {
  const stored = readStorage(BROWSER_ID_KEY);
  if (stored) return stored;
  const id = randomToken();
  writeStorage(BROWSER_ID_KEY, id);
  return id;
}

/** What the devices list calls this browser, such as "Firefox on macOS". */
export function browserDeviceName(): string {
  const parser = Bowser.getParser(navigator.userAgent);
  const browser = parser.getBrowserName() || "Browser";
  const os = parser.getOSName();
  return os ? `${browser} on ${os}` : browser;
}

/** The device this browser registered as for `userId`, if it has. */
export function cachedBrowserDeviceId(userId: number): string | null {
  return readStorage(`${DEVICE_KEY_PREFIX}${userId}`);
}

/**
 * The sync device this browser is for `userId`, registered on first use.
 *
 * Returns:
 *   The device id, or null when the account cannot register devices.
 */
export async function browserDeviceId(
  userId: number,
  { refresh = false }: { refresh?: boolean } = {},
): Promise<string | null> {
  const cached = cachedBrowserDeviceId(userId);
  if (cached && !refresh) return cached;

  try {
    const { data } = await syncApi.registerDevice({
      name: browserDeviceName(),
      platform: "Web",
      client: "web",
      hostname: browserId(),
      sync_mode: "api",
      allow_existing: true,
    });
    writeStorage(`${DEVICE_KEY_PREFIX}${userId}`, data.device_id);
    return data.device_id;
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 403) return null;
    throw error;
  }
}
