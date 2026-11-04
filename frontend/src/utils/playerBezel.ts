// Resolving the bezel overlay image the EmulatorJS player draws around a
// running game.
//
// ScreenScraper bezels live under the rom's resources folder, and
// `ss_metadata.bezel_path` stores the path relative to that folder
// (e.g. `roms/279/158934/bezel/bezel.png`). It must be prefixed with the
// resources base, exactly like covers / box-art (`FRONTEND_RESOURCES_PATH`),
// so the browser fetches the real image. Binding the raw relative path (as v1
// does) makes it resolve against the page URL, where RomM's SPA fallback hands
// back the app HTML instead of the PNG and the image never renders (#3939).
import { FRONTEND_RESOURCES_PATH } from "@/utils";

export function resolveBezelUrl(
  bezelPath: string | null | undefined,
): string | null {
  return bezelPath ? `${FRONTEND_RESOURCES_PATH}/${bezelPath}` : null;
}

// Where the bezel overlay should live for a given fullscreen state.
//
// EmulatorJS fullscreens its own `#game` container (tagged `.ejs_parent`) via
// the Fullscreen API, which promotes it to the top layer; a bezel that is only
// a sibling of `#game` then vanishes. So when that container is the fullscreen
// element, the bezel must teleport *into* it to keep framing the game. Any
// other (or absent) fullscreen element means render in place over the stage.
export function resolveBezelHost(
  fullscreenElement: Element | null,
): HTMLElement | null {
  if (
    fullscreenElement instanceof HTMLElement &&
    (fullscreenElement.id === "game" ||
      fullscreenElement.classList.contains("ejs_parent"))
  ) {
    return fullscreenElement;
  }
  return null;
}

// Whether the per-game bezel toggle should start on. Bezels default to shown;
// only an explicit "0" (the user hid a bad/misaligned bezel for this game)
// turns it off. Any other value fails safe to shown (#3939).
export function resolveStoredBezelVisible(stored: string | null): boolean {
  return stored !== "0";
}
