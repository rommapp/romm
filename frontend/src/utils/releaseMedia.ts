// A paused clip keeps its request open too, so only the clip played last may
// hold one. Hover previews have a slot of their own and never stop a clip.
type Holder = { el: HTMLMediaElement; onRelease: () => void };
const holders: { clip: Holder | null; preview: Holder | null } = {
  clip: null,
  preview: null,
};

// Dropping the src aborts the in-flight request; pause() alone keeps it open
// and ties up a browser connection.
export function releaseMedia(el: HTMLMediaElement) {
  if (holders.clip?.el === el) holders.clip = null;
  if (holders.preview?.el === el) holders.preview = null;
  el.pause();
  el.removeAttribute("src");
  el.load();
}

function displace(holder: Holder | null, el: HTMLMediaElement) {
  if (!holder || holder.el === el) return;
  releaseMedia(holder.el);
  holder.onRelease();
}

// Call when a clip starts playing. The clip and preview played before it are
// released, and their owners make them playable again (onRelease).
export function claimMedia(el: HTMLMediaElement, onRelease: () => void) {
  const { clip, preview } = holders;
  holders.clip = { el, onRelease };
  displace(clip, el);
  displace(preview, el);
}

// claimMedia for a hover preview: it only displaces the preview before it.
export function claimPreview(el: HTMLMediaElement, onRelease: () => void) {
  const { preview } = holders;
  holders.preview = { el, onRelease };
  displace(preview, el);
}
