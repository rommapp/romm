// Whether the mini player shows: a track is loaded and no full soundtrack
// player (the Jukebox, a game's Soundtrack subtab) is already on screen.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef } from "vue";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import { isJukeboxPlayerMode } from "@/v2/utils/jukebox";

export function useMiniPlayerVisible(): ComputedRef<boolean> {
  const route = useRoute();
  const { track } = storeToRefs(useSoundtrackPlayer());

  const onFullPlayer = computed(() => {
    const onJukeboxPlayer =
      route.name === ROUTES.MUSIC && isJukeboxPlayerMode(route.params.mode);
    const onGameSoundtrack =
      route.name === ROUTES.ROM &&
      route.query.tab === "media" &&
      route.query.subtab === "soundtrack";
    return onJukeboxPlayer || onGameSoundtrack;
  });

  return computed(() => track.value !== null && !onFullPlayer.value);
}
