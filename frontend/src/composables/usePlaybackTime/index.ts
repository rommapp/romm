// usePlaybackTime: the playing track's position, advanced every frame from
// the audio's coarse time reports so progress UI moves continuously.
import { useRafFn } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { ref, watch, type Ref } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";

export function usePlaybackTime(): Ref<number> {
  const { currentTime, duration, isPlaying, isBuffering } = storeToRefs(
    useSoundtrackPlayer(),
  );

  const time = ref(currentTime.value);
  let anchorTime = currentTime.value;
  let anchorStamp = performance.now();

  const frames = useRafFn(
    ({ timestamp }) => {
      const elapsed = (timestamp - anchorStamp) / 1000;
      const end = duration.value || Number.POSITIVE_INFINITY;
      time.value = Math.min(end, anchorTime + elapsed);
    },
    { immediate: false },
  );

  watch(currentTime, (reported) => {
    anchorTime = reported;
    anchorStamp = performance.now();
    time.value = reported;
  });

  watch(
    [isPlaying, isBuffering],
    ([playing, buffering]) => {
      frames.pause();
      if (!playing || buffering) return;
      anchorTime = time.value;
      anchorStamp = performance.now();
      frames.resume();
    },
    { immediate: true },
  );

  return time;
}
