// Pulls in md-editor with CodeMirror and its stylesheet, so import it lazily.
import { MdEditor } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { withoutCdn } from "./markdownNoCdn";

export default withoutCdn(MdEditor);
