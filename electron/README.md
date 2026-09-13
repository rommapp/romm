# RomM Desktop

An optional desktop shell for RomM. It loads your existing RomM server in a
native window and adds the one thing a browser cannot do: launching a game in a
locally installed emulator instead of an in-browser core.

This is a wrapper, not a fork of the web app. Nothing here changes how RomM
behaves in a normal browser, and the shell is not required to use RomM.

## What it does

- Opens your RomM server in a native window (no tabs, no address bar).
- Adds a "Play natively" action to games whose platform you have an emulator for.
- Downloads the ROM from your server, caches it locally, and launches it.
- Tracks the emulator process so the UI knows when a game is running.

Saves and states are left wherever the local emulator writes them. Syncing them
back to RomM is deliberately out of scope for this first version.

## Requirements

- A running RomM server you can already reach in a browser.
- An emulator. RetroArch is detected automatically; anything else is configured
  by hand (see below).

## Running it

```bash
cd electron
npm install
npm run dev
```

On first launch it asks for your server address, then loads it. Log in exactly
as you would in a browser; the shell holds no credentials of its own.

## Packaging

Not set up yet. Producing installers needs code signing to be useful (an Apple
Developer ID plus notarization on macOS, a signing certificate on Windows), so
the packaging toolchain lands with that rather than ahead of it. Until then the
shell runs from source with `npm run dev`.

## Emulator configuration

Config lives in `desktop-config.json` in Electron's `userData` directory:

| Platform | Path                                                             |
| -------- | ---------------------------------------------------------------- |
| Linux    | `~/.config/romm-desktop/desktop-config.json`                     |
| macOS    | `~/Library/Application Support/romm-desktop/desktop-config.json` |
| Windows  | `%APPDATA%\romm-desktop\desktop-config.json`                     |

### RetroArch (default)

RetroArch and its cores directory are detected from the usual install
locations. When a game is launched, RomM's own platform/core map decides which
libretro core to load, and the first core that is actually installed wins. Set
`retroarchPath` and `retroarchCoresPath` explicitly if your install is
somewhere unusual.

### Standalone emulators

`emulators` maps a platform to any executable. `{rom}` is replaced with the
cached ROM path and `{core}` with the resolved libretro core path. Each entry
is passed as a separate argument, so no shell is involved and paths with
spaces need no quoting.

```json
{
  "emulators": [
    {
      "platformSlug": "ps2",
      "label": "PCSX2",
      "command": "/usr/bin/pcsx2",
      "args": ["-batch", "{rom}"]
    },
    {
      "platformSlug": "*",
      "label": "RetroArch (Flatpak)",
      "command": "/usr/bin/flatpak",
      "args": ["run", "org.libretro.RetroArch", "-L", "{core}", "{rom}"]
    }
  ]
}
```

`platformSlug` uses RomM's own slugs (`snes`, `n64`, `ps2`). The `*` entry is
the fallback for any platform without its own row.

### ROM cache

Downloaded ROMs are cached under `cachePath` (defaults to `rom-cache` in the
same directory as the config). Once the cache exceeds `cacheLimitBytes`
(20 GB by default), least-recently-played ROMs are evicted.

## Security model

The window loads a remote origin and renders artwork and descriptions from ten
third-party metadata providers, so the renderer is treated as untrusted:

- `contextIsolation`, `sandbox`, and `nodeIntegration: false` are all enforced.
- In-window navigation is restricted to your server's origin; every other link
  is handed to your real browser.
- The renderer never supplies an executable or arguments. It names a game and
  the libretro cores its platform supports; the emulator command comes only
  from your own config.
- Core names are matched against `[a-z0-9_]+` before becoming a path, so they
  cannot point the loader outside the cores directory.
- Download URLs must resolve to the configured server origin and an `/api/`
  route.
- Processes are spawned with an argument array, never a shell string.

Self-signed certificates (common on a LAN) prompt once and are remembered by
fingerprint.

## Layout

```
src/
  main/             Main process
    config.ts       Persisted settings and emulator autodetection
    emulator/       Platform to emulator/core resolution
    launcher.ts     Download, resolve, spawn, track
    rom-cache.ts    Download with the window's session cookies, LRU cache
    safety.ts       Validation of everything the renderer sends
    window.ts       Window creation and navigation policy
  preload/          contextBridge surface (window.rommNative)
  shared/           Types shared with the RomM frontend
```
