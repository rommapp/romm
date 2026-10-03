// MdPreview and its stylesheet as one lazy-loadable chunk. A re-export, not a
// wrapper SFC, so callers keep MdPreview's prop types.
import "md-editor-v3/lib/style.css";

export { MdPreview as default } from "md-editor-v3";
