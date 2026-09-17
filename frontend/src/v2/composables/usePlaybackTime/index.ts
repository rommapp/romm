// usePlaybackTime — the playing track's position, advanced every frame from
// the audio's coarse time reports so progress UI moves continuously.
import { storeToRefs } from "pinia";
import { onScopeDispose, ref, watch, type Ref } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";

export function usePlaybackTime(): Ref<number> {
  const { currentTime, duration, isPlaying, isBuffering } = storeToRefs(
    useSoundtrackPlayer(),
  );

  const time = ref(currentTime.value);
  let anchorTime = currentTime.value;
  let anchorStamp = performance.now();
  let frame = 0;

  function tick(now: number) {
    const elapsed = (now - anchorStamp) / 1000;
    const end = duration.value || Number.POSITIVE_INFINITY;
    time.value = Math.min(end, anchorTime + elapsed);
    frame = requestAnimationFrame(tick);
  }

  function stop() {
    cancelAnimationFrame(frame);
    frame = 0;
  }

  watch(currentTime, (reported) => {
    anchorTime = reported;
    anchorStamp = performance.now();
    time.value = reported;
  });

  watch(
    [isPlaying, isBuffering],
    ([playing, buffering]) => {
      stop();
      if (!playing || buffering) return;
      anchorTime = time.value;
      anchorStamp = performance.now();
      frame = requestAnimationFrame(tick);
    },
    { immediate: true },
  );

  onScopeDispose(stop);

  return time;
}
