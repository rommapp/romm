// Two-way binding between the jukebox's browse state and the URL: the mode
// is a path segment written with `push` (every subgroup is a history entry);
// the selection inside a mode is query state written with `replace`.
import { computed, ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import { parseJukeboxMode, type JukeboxMode } from "@/v2/utils/jukebox";
import { patchQuery } from "@/v2/utils/routeQuery";

function readParam(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function useJukeboxUrlState() {
  const route = useRoute();
  const router = useRouter();

  const mode = ref<JukeboxMode>(parseJukeboxMode(route.params.mode));

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

  /** The location for a mode, carrying only the selection params that make
   *  sense inside it so a copied link never holds a stale filter. */
  function locationFor(value: JukeboxMode) {
    return {
      name: ROUTES.MUSIC,
      params: { mode: value === "home" ? "" : value },
      query: {
        game: value === "album" ? game.value || undefined : undefined,
        artist: value === "artist" ? artist.value || undefined : undefined,
        genre: value === "genre" ? genre.value || undefined : undefined,
        platform:
          value === "platform" ? platform.value || undefined : undefined,
        decade: value === "decade" ? decade.value || undefined : undefined,
        search: value === "album" ? search.value || undefined : undefined,
      },
    };
  }

  // URL -> ref: back/forward and direct navigation drive the mode.
  watch(
    () => route.params.mode,
    (value) => {
      const next = parseJukeboxMode(value);
      if (next !== mode.value) mode.value = next;
    },
  );

  // ref -> URL: in-app mode switches push a new history entry.
  watch(mode, (value) => {
    if (parseJukeboxMode(route.params.mode) === value) return;
    void router.push(locationFor(value));
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
