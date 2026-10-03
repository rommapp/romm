// md-editor and its stylesheet as one lazy-loadable chunk. Re-exported, not
// wrapped in an SFC, so callers keep the components' prop and v-model types.
import "md-editor-v3/lib/style.css";

export { MdEditor, MdPreview } from "md-editor-v3";
