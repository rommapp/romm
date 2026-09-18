import { ref } from "vue";

// Scroll depth (px) past which the top bar switches to its glass surface.
const THRESHOLD = 4;

// Views that scroll an inner container instead of the document (the gallery
// shells) report it here so the top bar turns to glass over them as well.
const innerScrolled = ref(false);

// A toolbar pinned right under the top bar paints one glass across both, so
// the top bar drops its own (two blurred boxes never match at their edge).
const innerGlass = ref(false);

export function useNavGlass() {
  return { innerScrolled, innerGlass, threshold: THRESHOLD };
}
