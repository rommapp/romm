// MdEditor and its stylesheet as one lazy-loadable chunk. A re-export, not a
// wrapper SFC, so callers keep MdEditor's prop and v-model types.
import "md-editor-v3/lib/style.css";

export { MdEditor as default } from "md-editor-v3";
