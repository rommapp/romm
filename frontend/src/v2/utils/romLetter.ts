// Shared letter-bucketing logic for ROM titles. Must mirror the backend's
// sort/group key, which strips a leading article before computing positions
// and `char_index`. If we don't strip the same way, "The Legend of Zelda"
// lands under T on the frontend while the backend has it under L, so the
// AlphaStrip and the gallery disagree.
//
// Keep the article list below in sync with ARTICLES in backend/models/rom.py.
import type { SimpleRom } from "@/stores/roms";

const STRIP_ARTICLES =
  /^\s*(?:the|a|an|le|la|les|el|los|las|il|lo|gli|der|die|das|het)\s+/i;

export function romBucketLetter(rom: SimpleRom): string {
  const raw = rom.name || rom.fs_name_no_ext || "";
  const stripped = raw.replace(STRIP_ARTICLES, "").trim();
  const c = stripped.charAt(0).toUpperCase();
  if (!c) return "#";
  return /[A-Z]/.test(c) ? c : "#";
}
