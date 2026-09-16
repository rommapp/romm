// Cross-document page transitions for the isolated players.
//
// EmulatorJS and js-dos launch through a full document load (see
// useGameActions.play), so the same-document morphs in useViewTransition cannot
// span it. A cross-document transition can, but it is only ever performed when
// *both* documents opt in, and neither opt-in is static here: a static
// `@view-transition` would be inherited by every page, so every other hard
// navigation would opt in too and then cross-fade, or fail to line up with an
// incoming document that did not. So the launch arms the descriptor on both
// ends, and the marker is what tells the player document to arm it.
//
// The stored path is matched against the loaded document's own path, so a
// marker left behind by a launch that never happened cannot decorate an
// unrelated navigation.
//
// The player end runs before the bundle exists, so the key and the at-rule are
// repeated in index.html; keep the two in step.
const NAV_KEY = "romm-xdoc-nav";

const OPT_IN = "@view-transition { navigation: auto; }";

/** Opt this document into a cross-document transition and record where it is
 *  going. Call immediately before `window.location.assign`. */
export function armCrossDocumentTransition(path: string): void {
  try {
    sessionStorage.setItem(NAV_KEY, path);
  } catch {
    // Storage can throw (private mode, quota). Without the marker the player
    // document cannot know to opt in, so leave this end unarmed too: a
    // transition with one end missing is aborted and logs a console error.
    return;
  }
  const style = document.createElement("style");
  style.textContent = OPT_IN;
  document.head.append(style);
}
