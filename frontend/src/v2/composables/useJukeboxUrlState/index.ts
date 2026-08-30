// Two-way binding between the jukebox's browse state and the URL.
//
// Mode and the current selection are bookmarkable session state (constitution
// §VI.D), so they live in the query string. Every param goes through the same
// `queryRef` helper rather than a hand-written ref + watcher pair per param,
// which is what let `artist` silently miss its URL->ref direction before.
import { computed, ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { modeFromQuery, type JukeboxMode } from "@/v2/utils/jukebox";
import { patchQuery } from "@/v2/utils/routeQuery";

function readParam(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function useJukeboxUrlState() {
  const route = useRoute();
  const router = useRouter();

  const mode = ref<JukeboxMode>(modeFromQuery(route.query.mode));

  /** A ref mirrored into `?key=`; writes are merged by `patchQuery`. */
  function queryRef(key: string): Ref<string> {
    const state = ref(readParam(route.query[key]));
    watch(
      () => route.query[key],
      (next) => {
        const value = readParam(next);
        if (value !== state.value) state.value = value;
      },
    );
    watch(state, (value) => {
      patchQuery(router, { [key]: value || undefined });
    });
    return state;
  }

  const search = queryRef("search");
  const artist = queryRef("artist");
  const genre = queryRef("genre");
  const platform = queryRef("platform");
  const decade = queryRef("decade");
  const game = queryRef("game");

  watch(
    () => route.query.mode,
    (value) => {
      const next = modeFromQuery(value);
      if (next !== mode.value) mode.value = next;
    },
  );

  // Leaving a mode drops the selection params that only make sense inside it,
  // so a copied link never carries a stale filter from a previous screen.
  watch(mode, (value) => {
    patchQuery(router, {
      mode: value === "home" ? undefined : value,
      game: value === "album" ? game.value || undefined : undefined,
      artist: value === "artist" ? artist.value || undefined : undefined,
      genre: value === "genre" ? genre.value || undefined : undefined,
      platform: value === "platform" ? platform.value || undefined : undefined,
      decade: value === "decade" ? decade.value || undefined : undefined,
      search: value === "album" ? search.value || undefined : undefined,
    });
  });

  const selectedPlatformId = computed(() => Number(platform.value) || 0);
  const selectedDecade = computed(() => Number(decade.value) || 0);
  const selectedRomId = computed(() => Number(game.value) || 0);

  return {
    mode,
    search,
    artist,
    genre,
    platform,
    decade,
    game,
    selectedPlatformId,
    selectedDecade,
    selectedRomId,
  };
}
