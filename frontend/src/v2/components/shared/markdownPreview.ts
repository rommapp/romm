// Pulls in md-editor's renderer and stylesheet, so import it lazily. Kept apart
// from markdownEditor.ts so a preview never downloads CodeMirror.
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { withoutCdn } from "./markdownNoCdn";

export default withoutCdn(MdPreview);
