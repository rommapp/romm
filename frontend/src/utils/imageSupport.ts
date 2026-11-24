// Browsers disagree on JPEG XL, so library .jxl files are only listed where a
// probe image actually decodes, instead of as broken tiles.
import { ref } from "vue";

// A lossless 1x1 red JPEG XL (22 bytes).
const JXL_PROBE = "data:image/jxl;base64,/woAEBAJCAABACgASxiLFcJJQU5/AA==";

const jxlDecodes = ref(false);
let probeStarted = false;

function probeJxl() {
  if (probeStarted || typeof Image === "undefined") return;
  probeStarted = true;
  const img = new Image();
  img.onload = () => {
    jxlDecodes.value = img.naturalWidth > 0;
  };
  img.src = JXL_PROBE;
}

/** Reactive browser support for JPEG XL, false until the probe decodes. */
export function canRenderJxl(): boolean {
  probeJxl();
  return jxlDecodes.value;
}

/** Whether a library image with this lowercase extension can be shown. */
export function isRenderableImageExtension(
  ext: string,
  extensions: ReadonlySet<string>,
): boolean {
  if (!extensions.has(ext)) return false;
  return ext !== "jxl" || canRenderJxl();
}
