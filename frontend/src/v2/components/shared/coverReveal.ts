// Session-shared set of cover URLs that have finished loading (bloomed) at
// least once. GameCover reads it so a recycled card (virtual scroll) pointing
// at an already-seen URL skips the blur-up reveal: replaying the
// `filter: blur(16px)` bloom on every remount is just flicker, and during the
// gallery's re-packs — which remount cards as positions shuffle between rows —
// that per-card blur cost compounds into real jank.
//
// Module-level so the state is shared across every GameCover instance. Bounded
// by the count of unique covers seen this session; reset on reload.
export const revealedCoverSrcs = new Set<string>();
