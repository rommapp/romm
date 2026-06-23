// Procedural "no cover" artwork — v2 port of v1's `utils/covers`.
//
// When a rom has no cover image we paint a generated SVG keyed off the
// rom's name: a coloured backdrop with two organic blobs (positioned +
// rotated by a hash of the name, so every game gets a distinct-but-stable
// look) and a centred icon — a grid for identified roms ("missing" cover)
// or a question mark for unidentified ones ("unmatched").
//
// Differences from v1:
//   * Colours come from the `colorCoverArt` token (no hex literals here).
//   * Returns a `data:` URI instead of a Blob object URL — cacheable and
//     leak-free (v1's `URL.createObjectURL` was never revoked).
import { colorCoverArt } from "@/v2/tokens";

function hashString(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 100);
  }
  return Math.abs(h);
}

function translatedBGs(str: string) {
  const h = hashString(str);
  return {
    left: { x: -150 + (h % 100), y: -75 + (h % 50) },
    right: { x: 350 - (h % 100), y: 250 - (h % 50) },
  };
}

function bgRotation(str: string): number {
  return hashString(str) % 60;
}

function svgToDataUri(svg: string): string {
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

// Shared backdrop + two hashed blobs. `inner` is the centred foreground
// markup (icon) layered on top.
function buildArt(name: string, inner: string): string {
  const t = translatedBGs(name);
  const r = bgRotation(name);
  const { base, shade, warm } = colorCoverArt;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="${base}" d="M0 0h600v800H0z"/><path fill="${shade}" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${t.left.x}px,${t.left.y}px) rotate(${r}deg);"/><path fill="${warm}" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${t.right.x}px,${t.right.y}px) rotate(${r}deg);"/>${inner}</g><defs><mask id="a"><path fill="white" d="M0 0h600v800H0z"/></mask></defs></svg>`;
  return svgToDataUri(svg);
}

/** Identified rom with no cover — backdrop + grid-of-dots icon. */
export function getMissingCoverImage(name: string): string {
  const icoR = [90, 0, 270, 180][hashString(name) % 4];
  const icon = `<path d="M204.545 345.455A54.545 54.545 0 0 1 259.091 400a54.545 54.545 0 0 1-54.546 54.545A54.545 54.545 0 0 1 150 400a54.545 54.545 0 0 1 54.545-54.545M300 250a54.545 54.545 0 0 1 54.545 54.545A54.545 54.545 0 0 1 300 359.091a54.545 54.545 0 0 1-54.545-54.546A54.545 54.545 0 0 1 300 250m0 190.91a54.545 54.545 0 0 1 54.545 54.545A54.545 54.545 0 0 1 300 550a54.545 54.545 0 0 1-54.545-54.545A54.545 54.545 0 0 1 300 440.909m95.455-95.454A54.545 54.545 0 0 1 450 400a54.545 54.545 0 0 1-54.545 54.545A54.545 54.545 0 0 1 340.909 400a54.545 54.545 0 0 1 54.546-54.545m-190.91 27.272A27.273 27.273 0 0 0 177.273 400a27.273 27.273 0 0 0 27.272 27.273A27.273 27.273 0 0 0 231.818 400a27.273 27.273 0 0 0-27.273-27.273m190.91 0A27.273 27.273 0 0 0 368.182 400a27.273 27.273 0 0 0 27.273 27.273A27.273 27.273 0 0 0 422.727 400a27.273 27.273 0 0 0-27.272-27.273M300 468.182a27.273 27.273 0 0 0-27.273 27.273A27.273 27.273 0 0 0 300 522.727a27.273 27.273 0 0 0 27.273-27.272A27.273 27.273 0 0 0 300 468.182" style="fill:${colorCoverArt.icon};stroke-width:13.6364;transform-origin:center;transform:rotate(${icoR}deg);"/>`;
  return buildArt(name, icon);
}

/** Unidentified rom — backdrop + question-mark icon. */
export function getUnmatchedCoverImage(name: string): string {
  const icon = `<path d="M300 225c-8.748 0-17.496 3.324-24.669 10.322L135.366 375.287a34.536 34.536 0 0 0 0 49.338L275.331 564.59a34.536 34.536 0 0 0 49.338 0l139.965-139.965a34.536 34.536 0 0 0 0-49.338L324.669 235.322C317.496 228.324 308.748 225 300 225m0 86.603c47.238 1.925 67.708 49.513 39.89 85.03-7.348 8.747-19.07 14.52-25.019 22.044-6.123 7.523-6.123 16.27-6.123 25.018h-26.244c0-14.871 0-27.293 6.124-36.04 5.773-8.748 17.495-13.997 24.844-19.77 21.52-19.77 15.92-47.589-13.472-49.863-14.346 0-26.243 11.722-26.243 26.418h-26.244c0-29.218 23.62-52.837 52.487-52.837m-17.496 149.588h26.244v26.243h-26.244z" style="fill:${colorCoverArt.icon};stroke-width:17.4956"/>`;
  return buildArt(name, icon);
}

/** Pick the right generated art for a rom: grid for identified roms,
 *  question mark for unmatched ones. */
export function coverPlaceholderArt(name: string, identified: boolean): string {
  return identified ? getMissingCoverImage(name) : getUnmatchedCoverImage(name);
}

/** Backdrop-only art (no icon) sized to an arbitrary aspect ratio — used
 *  for non-cover thumbnails (e.g. save / state assets). The viewBox is
 *  re-centred so the blobs stay framed at any ratio. */
export function getEmptyCoverImage(name: string, aspectRatio = 2 / 3): string {
  const t = translatedBGs(name);
  const r = bgRotation(name);
  const { base, shade, warm } = colorCoverArt;
  const width = 600;
  const height = width / aspectRatio;
  const designHeight = 800;
  const yOffset = (designHeight - height) / 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 ${yOffset} ${width} ${height}"><g fill="none" mask="url(#a)"><path fill="${base}" d="M0 0h${width}v${designHeight}H0z"/><path fill="${shade}" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${t.left.x}px,${t.left.y}px) rotate(${r}deg);"/><path fill="${warm}" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${t.right.x}px,${t.right.y}px) rotate(${r}deg);"/></g><defs><mask id="a"><path fill="white" d="M0 0h${width}v${designHeight}H0z"/></mask></defs></svg>`;
  return svgToDataUri(svg);
}
