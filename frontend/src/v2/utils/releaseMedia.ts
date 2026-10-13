// Dropping the src aborts the in-flight request; pause() alone keeps it open
// and ties up a browser connection.
export function releaseMedia(el: HTMLMediaElement) {
  el.pause();
  el.removeAttribute("src");
  el.load();
}
