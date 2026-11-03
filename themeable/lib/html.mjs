// Adds the loader to RomM's built index.html. The tag goes last in <head> so the
// theme stylesheet it inserts lands after the app's own CSS.
export const LOADER_TAG = '<script src="/themeable/loader.js"></script>';
const MARKER = "<!-- themeable -->";

export function injectLoader(html) {
  if (html.includes(MARKER)) return html;
  const at = html.lastIndexOf("</head>");
  if (at < 0) throw new Error("index.html has no </head>; upstream changed its entry page");
  return `${html.slice(0, at).trimEnd()}\n    ${MARKER}\n    ${LOADER_TAG}\n  ${html.slice(at)}`;
}
