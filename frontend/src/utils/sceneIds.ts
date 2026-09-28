/** Parse a Demozoo / Pouët / CSDb production id from a pasted number or URL. */

export type SceneIdKind = "demozoo" | "pouet" | "csdb";

export function parseSceneId(
  raw: string | number | null | undefined,
  kind: SceneIdKind,
): number | null {
  if (raw == null) return null;
  const text = String(raw).trim();
  if (text === "") return null;
  if (/^\d+$/.test(text)) return Number.parseInt(text, 10);

  let url: URL;
  try {
    url = new URL(text);
  } catch {
    const n = Number.parseInt(text, 10);
    return Number.isNaN(n) ? null : n;
  }

  const host = url.hostname.replace(/^www\./i, "").toLowerCase();

  if (kind === "demozoo" && host === "demozoo.org") {
    const match = url.pathname.match(/\/(?:api\/v1\/)?productions\/(\d+)/i);
    return match ? Number.parseInt(match[1], 10) : null;
  }

  if (kind === "pouet" && host === "pouet.net") {
    const which = url.searchParams.get("which");
    if (which && /^\d+$/.test(which)) return Number.parseInt(which, 10);
    return null;
  }

  if (kind === "csdb" && host === "csdb.dk") {
    const id = url.searchParams.get("id");
    if (id && /^\d+$/.test(id)) return Number.parseInt(id, 10);
    const match = url.pathname.match(/\/release\/(\d+)/i);
    return match ? Number.parseInt(match[1], 10) : null;
  }

  return null;
}
