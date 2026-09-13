import { app } from "electron";
import { existsSync } from "node:fs";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import {
  DEFAULT_CACHE_LIMIT_BYTES,
  type DesktopConfig,
} from "../shared/types.ts";

const CONFIG_FILE = "desktop-config.json";

function emptyConfig(): DesktopConfig {
  return {
    serverUrl: null,
    retroarchPath: null,
    retroarchCoresPath: null,
    emulators: [],
    cachePath: null,
    cacheLimitBytes: DEFAULT_CACHE_LIMIT_BYTES,
    trustedCertificates: [],
  };
}

/** Common install locations, most specific first. */
function retroarchCandidates(): string[] {
  const home = homedir();
  switch (process.platform) {
    case "darwin":
      return [
        "/Applications/RetroArch.app/Contents/MacOS/RetroArch",
        join(home, "Applications/RetroArch.app/Contents/MacOS/RetroArch"),
      ];
    case "win32":
      return [
        "C:\\RetroArch-Win64\\retroarch.exe",
        join(home, "scoop\\apps\\retroarch\\current\\retroarch.exe"),
      ];
    default:
      return [
        "/usr/bin/retroarch",
        "/usr/local/bin/retroarch",
        join(home, ".local/bin/retroarch"),
      ];
  }
}

function coresCandidates(retroarchPath: string | null): string[] {
  const home = homedir();
  const candidates: string[] = [];
  switch (process.platform) {
    case "darwin":
      candidates.push(
        join(home, "Library/Application Support/RetroArch/cores"),
      );
      break;
    case "win32":
      if (retroarchPath) candidates.push(join(dirname(retroarchPath), "cores"));
      break;
    default:
      candidates.push(
        join(home, ".config/retroarch/cores"),
        join(home, ".var/app/org.libretro.RetroArch/config/retroarch/cores"),
        "/usr/lib/libretro",
        "/usr/lib/x86_64-linux-gnu/libretro",
      );
  }
  return candidates;
}

function firstExisting(paths: string[]): string | null {
  return paths.find((candidate) => existsSync(candidate)) ?? null;
}

/**
 * Fill in anything the user has not configured by probing the filesystem, so a
 * standard RetroArch install works with no setup.
 */
export function withDetectedDefaults(config: DesktopConfig): DesktopConfig {
  const retroarchPath =
    config.retroarchPath ?? firstExisting(retroarchCandidates());
  return {
    ...config,
    retroarchPath,
    retroarchCoresPath:
      config.retroarchCoresPath ??
      firstExisting(coresCandidates(retroarchPath)),
    cachePath: config.cachePath ?? join(app.getPath("userData"), "rom-cache"),
  };
}

function configPath(): string {
  return join(app.getPath("userData"), CONFIG_FILE);
}

let cached: DesktopConfig | null = null;

export async function loadConfig(): Promise<DesktopConfig> {
  if (cached) return cached;
  try {
    const raw = await readFile(configPath(), "utf8");
    const parsed = JSON.parse(raw) as Partial<DesktopConfig>;
    cached = withDetectedDefaults({ ...emptyConfig(), ...parsed });
  } catch {
    // A missing or corrupt config is not fatal: fall back to detection and let
    // the next save rewrite the file.
    cached = withDetectedDefaults(emptyConfig());
  }
  return cached;
}

export async function saveConfig(next: DesktopConfig): Promise<void> {
  cached = next;
  const target = configPath();
  await mkdir(dirname(target), { recursive: true });
  // Write-then-rename so a crash mid-write cannot leave a truncated config.
  const temp = `${target}.tmp`;
  await writeFile(temp, JSON.stringify(next, null, 2), "utf8");
  await rename(temp, target);
}

export async function updateConfig(
  patch: Partial<DesktopConfig>,
): Promise<DesktopConfig> {
  const next = { ...(await loadConfig()), ...patch };
  await saveConfig(next);
  return next;
}
