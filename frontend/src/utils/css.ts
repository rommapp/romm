// Build a safe CSS `url("...")` token from a raw URL string.
// Quoting is required for paths containing spaces or brackets.
export function toCssUrl(url: string): string {
  const escaped = url
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/[\n\r\f]/g, "");
  return `url("${escaped}")`;
}
