// md-editor's renderer, its stylesheet and its config as one lazy chunk. Kept
// apart from markdownEditor.ts so a preview never downloads CodeMirror.
import "md-editor-v3/lib/style.css";
import "@/plugins/mdeditor";

export { MdPreview as default } from "md-editor-v3";
