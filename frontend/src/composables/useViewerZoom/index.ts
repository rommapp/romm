// useViewerZoom: the fit mode and zoom level shared by the document viewers.
// Zoom is a factor over the fitted size, so 1 is the fit itself; the fit
// persists per user and viewer, the zoom lasts the session.
import { computed, ref } from "vue";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";

export type FitMode = "page" | "width";

export const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4] as const;

const MIN_ZOOM = ZOOM_STEPS[0];
const MAX_ZOOM = ZOOM_STEPS[ZOOM_STEPS.length - 1] ?? 1;
// A zoom set from outside (pdf.js's Ctrl+wheel) rarely lands on a step, so a
// step only counts as the next one when it is clearly past the current zoom.
const EPSILON = 0.01;

export function useViewerZoom(storageKey: string, defaultFit: FitMode) {
  const fit = useUserLocalStorage<FitMode>(storageKey, defaultFit);
  const zoom = ref(1);

  const canZoomIn = computed(() => zoom.value < MAX_ZOOM - EPSILON);
  const canZoomOut = computed(() => zoom.value > MIN_ZOOM + EPSILON);

  function zoomIn(): boolean {
    const next = ZOOM_STEPS.find((step) => step > zoom.value + EPSILON);
    if (next === undefined) return false;
    zoom.value = next;
    return true;
  }

  function zoomOut(): boolean {
    const next = [...ZOOM_STEPS]
      .reverse()
      .find((step) => step < zoom.value - EPSILON);
    if (next === undefined) return false;
    zoom.value = next;
    return true;
  }

  /** Switch between fit modes, back at the fitted size. */
  function toggleFit() {
    fit.value = fit.value === "page" ? "width" : "page";
    zoom.value = 1;
  }

  return { fit, zoom, canZoomIn, canZoomOut, zoomIn, zoomOut, toggleFit };
}
