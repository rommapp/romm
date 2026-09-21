/** Save a blob to the user's disk under `filename`. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** The filename a `Content-Disposition` header asks for, or `fallback`. */
export function filenameFromResponse(
  disposition: unknown,
  fallback: string,
): string {
  const match = /filename="?([^";]+)"?/.exec(String(disposition ?? ""));
  return match ? match[1] : fallback;
}
