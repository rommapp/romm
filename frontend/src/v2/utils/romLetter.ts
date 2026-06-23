// Shared letter-bucketing logic for ROM titles. Must mirror the backend's
// sort/group key — the API strips the leading article (`the`, `a`, `an`)
// before computing positions and `char_index`. If we don't strip the
// same way, "The Legend of Zelda" lands under T on the frontend while
// the backend has it under L → the AlphaStrip and the gallery disagree.
//
// Backend reference: STRIP_ARTICLES_REGEX = r"^(the|a|an)\s+" applied to
// `lower(name)` before extracting the first character (see
// backend/handler/database/roms_handler.py).
import type { SimpleRom } from "@/stores/roms";

const STRIP_ARTICLES = /^\s*(?:the|a|an)\s+/i;

export function romBucketLetter(rom: SimpleRom): string {
  const raw = rom.name || rom.fs_name_no_ext || "";
  const stripped = raw.replace(STRIP_ARTICLES, "").trim();
  const c = stripped.charAt(0).toUpperCase();
  if (!c) return "#";
  return /[A-Z]/.test(c) ? c : "#";
}
