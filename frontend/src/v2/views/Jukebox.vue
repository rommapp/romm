<script setup lang="ts">
import {
  RBtn,
  RChip,
  RDivider,
  RIcon,
  RList,
  RListItem,
  RPlatformIcon,
  RSkeletonBlock,
  RTextField,
} from "@v2/lib";
import axios from "axios";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type { MusicTrackSchema } from "@/__generated__";
import musicApi from "@/services/api/music";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import SoundtrackPanel from "@/v2/components/GameDetails/SoundtrackPanel.vue";
import CardRow from "@/v2/components/Home/CardRow.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import { useCan } from "@/v2/composables/useCan";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";
import {
  buildFreeRadioSession,
  trackDurationSeconds,
} from "@/v2/utils/freeRadio";
import {
  type JukeboxMode,
  type JukeboxPlayerMode,
  modeFromQuery,
} from "@/v2/utils/jukebox";
import { patchQuery } from "@/v2/utils/routeQuery";

interface DecadeGroup {
  startYear: number;
  label: string;
  tracks: MusicTrackSchema[];
}

interface ArtistGroup {
  name: string;
  tracks: MusicTrackSchema[];
}

interface Album {
  romId: number;
  title: string;
  platform: string;
  coverUrl?: string;
  trackCount: number;
}

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const confirm = useConfirm();
const snackbar = useSnackbar();
const canEdit = useCan("rom.edit");
const mode = ref<JukeboxMode>(modeFromQuery(route.query.mode));

function openMode(value: JukeboxPlayerMode) {
  if (value === "station") generateFreeRadio();
  mode.value = value;
}

function openHome() {
  mode.value = "home";
}

const tracks = ref<MusicTrackSchema[]>([]);
const allTracks = ref<MusicTrackSchema[]>([]);
const freeRadioTracks = ref<MusicTrackSchema[]>([]);
const loadingAllTracks = ref(true);
const selectedRomId = ref<number | null>(null);
const selectedArtist = ref(
  typeof route.query.artist === "string" ? route.query.artist : "",
);
const artistSearch = ref("");
const selectedDecade = ref(Number(route.query.decade) || 0);
const selectedGenre = ref(
  typeof route.query.genre === "string" ? route.query.genre : "",
);
const selectedPlatformId = ref(Number(route.query.platform) || 0);
const selectedRom = ref<DetailedRom | null>(null);
const loadingAlbums = ref(true);
const loadingRom = ref(false);
const albumsFailed = ref(false);
const romFailed = ref(false);
const search = ref(
  typeof route.query.search === "string" ? route.query.search : "",
);

let albumFetchToken = 0;
let romFetchToken = 0;
let romAbort: AbortController | null = null;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

function pushGrouped<K>(
  grouped: Map<K, MusicTrackSchema[]>,
  key: K,
  track: MusicTrackSchema,
) {
  const existing = grouped.get(key);
  if (existing) existing.push(track);
  else grouped.set(key, [track]);
}

const albums = computed<Album[]>(() => {
  const grouped = new Map<number, Album>();
  for (const track of tracks.value) {
    const album = grouped.get(track.rom_id);
    if (album) {
      album.trackCount += 1;
      if (!album.coverUrl && track.game_cover_url) {
        album.coverUrl = track.game_cover_url;
      }
      continue;
    }
    grouped.set(track.rom_id, {
      romId: track.rom_id,
      title: track.game_name || track.album || String(track.rom_id),
      platform: track.platform_name,
      coverUrl: track.game_cover_url || undefined,
      trackCount: 1,
    });
  }
  return [...grouped.values()].sort((a, b) => a.title.localeCompare(b.title));
});

const decades = computed<DecadeGroup[]>(() => {
  const grouped = new Map<number, MusicTrackSchema[]>();
  for (const track of allTracks.value) {
    if (!track.year) continue;
    const startYear = Math.floor(track.year / 10) * 10;
    pushGrouped(grouped, startYear, track);
  }
  return [...grouped.entries()]
    .map(([startYear, decadeTracks]) => ({
      startYear,
      label: `${startYear}s`,
      tracks: decadeTracks,
    }))
    .sort((a, b) => b.startYear - a.startYear);
});

const favoriteTracks = computed(() =>
  allTracks.value.filter((track) => track.is_favorite),
);

const genres = computed(() => {
  const grouped = new Map<string, MusicTrackSchema[]>();
  for (const track of allTracks.value) {
    for (const genre of track.game_genres ?? []) {
      const name = genre.trim();
      if (!name) continue;
      pushGrouped(grouped, name, track);
    }
  }
  return [...grouped.entries()]
    .map(([name, genreTracks]) => ({ name, tracks: genreTracks }))
    .sort((a, b) => a.name.localeCompare(b.name));
});

const platforms = computed(() => {
  const grouped = new Map<
    number,
    {
      id: number;
      name: string;
      slug: string;
      tracks: MusicTrackSchema[];
    }
  >();
  for (const track of allTracks.value) {
    const group = grouped.get(track.platform_id) ?? {
      id: track.platform_id,
      name: track.platform_name,
      slug: track.platform_slug,
      tracks: [],
    };
    group.tracks.push(track);
    grouped.set(track.platform_id, group);
  }
  return [...grouped.values()].sort((a, b) => a.name.localeCompare(b.name));
});

const recentlyAddedTracks = computed(() =>
  allTracks.value
    .map((track) => ({ track, addedAt: Date.parse(track.added_at) }))
    .sort((a, b) => b.addedAt - a.addedAt)
    .slice(0, 25)
    .map((entry) => entry.track),
);

const selectedGenreTracks = computed(
  () =>
    genres.value.find((genre) => genre.name === selectedGenre.value)?.tracks ??
    [],
);
const selectedPlatformTracks = computed(
  () =>
    platforms.value.find((platform) => platform.id === selectedPlatformId.value)
      ?.tracks ?? [],
);

function selectGenre(genre: { name: string }) {
  selectedGenre.value = genre.name;
  patchQuery(router, { genre: genre.name });
}

function selectPlatform(platform: { id: number }) {
  selectedPlatformId.value = platform.id;
  patchQuery(router, { platform: String(platform.id) });
}

const selectedDecadeTracks = computed(
  () =>
    decades.value.find((decade) => decade.startYear === selectedDecade.value)
      ?.tracks ?? [],
);

function selectDecade(decade: DecadeGroup) {
  selectedDecade.value = decade.startYear;
  patchQuery(router, { decade: String(decade.startYear) });
}

const artists = computed<ArtistGroup[]>(() => {
  const grouped = new Map<string, MusicTrackSchema[]>();
  for (const track of allTracks.value) {
    const name = track.artist?.trim();
    if (!name) continue;
    pushGrouped(grouped, name, track);
  }
  return [...grouped.entries()]
    .map(([name, artistTracks]) => ({ name, tracks: artistTracks }))
    .sort((a, b) => a.name.localeCompare(b.name));
});

const filteredArtists = computed(() => {
  const query = artistSearch.value.trim().toLocaleLowerCase();
  return query
    ? artists.value.filter((artist) =>
        artist.name.toLocaleLowerCase().includes(query),
      )
    : artists.value;
});

const selectedArtistTracks = computed(
  () =>
    artists.value.find((artist) => artist.name === selectedArtist.value)
      ?.tracks ?? [],
);

function selectArtist(artist: ArtistGroup) {
  selectedArtist.value = artist.name;
  patchQuery(router, { artist: artist.name });
}

// The four "one big list" modes; `sessionTracks` is the single source for
// both the emptiness check and the panel's input.
const SESSION_MODES = ["play-all", "station", "favorite", "recent"] as const;

const isSessionMode = computed(() =>
  (SESSION_MODES as readonly string[]).includes(mode.value),
);

const sessionTracks = computed<MusicTrackSchema[]>(() => {
  if (mode.value === "station") return freeRadioTracks.value;
  if (mode.value === "favorite") return favoriteTracks.value;
  if (mode.value === "recent") return recentlyAddedTracks.value;
  return allTracks.value;
});

const freeRadioDuration = computed(() =>
  trackDurationSeconds(freeRadioTracks.value),
);

function generateFreeRadio() {
  freeRadioTracks.value = buildFreeRadioSession(allTracks.value);
}

interface LaunchTile {
  mode: JukeboxPlayerMode;
  icon: string;
  label: string;
  count: string;
}

function tracksCount(n: number): string {
  return t("rom.tracks-n", n, { named: { n } });
}

const launchRows = computed<{ title: string; tiles: LaunchTile[] }[]>(() => [
  {
    title: t("common.playlists"),
    tiles: [
      {
        mode: "station",
        icon: "mdi-radio-tower",
        label: t("common.free-radio"),
        count: formatRadioDuration(freeRadioDuration.value),
      },
      {
        mode: "decade",
        icon: "mdi-calendar-range",
        label: t("common.decade-mix"),
        count: t("common.decades-n", decades.value.length, {
          named: { n: decades.value.length },
        }),
      },
      {
        mode: "recent",
        icon: "mdi-clock-outline",
        label: t("common.recently-added-soundtracks"),
        count: tracksCount(recentlyAddedTracks.value.length),
      },
      {
        mode: "favorite",
        icon: "mdi-heart",
        label: t("common.favorite-soundtracks"),
        count: tracksCount(favoriteTracks.value.length),
      },
    ],
  },
  {
    title: t("common.library"),
    tiles: [
      {
        mode: "play-all",
        icon: "mdi-playlist-music",
        label: t("common.play-all"),
        count: tracksCount(allTracks.value.length),
      },
      {
        mode: "album",
        icon: "mdi-album",
        label: t("common.music-by-album"),
        count: t("common.albums-n", albums.value.length, {
          named: { n: albums.value.length },
        }),
      },
      {
        mode: "platform",
        icon: "mdi-controller",
        label: t("common.soundtracks-by-platform"),
        count: t("common.platforms-n", platforms.value.length, {
          named: { n: platforms.value.length },
        }),
      },
      {
        mode: "artist",
        icon: "mdi-account-music",
        label: t("common.music-by-artist"),
        count: t("common.artists-n", artists.value.length, {
          named: { n: artists.value.length },
        }),
      },
      {
        mode: "genre",
        icon: "mdi-shape",
        label: t("common.soundtracks-by-genre"),
        count: t("common.genres-n", genres.value.length, {
          named: { n: genres.value.length },
        }),
      },
    ],
  },
]);

function formatRadioDuration(seconds: number): string {
  return t("common.minutes-n", { n: Math.ceil(seconds / 60) });
}

async function loadRom(romId: number) {
  const token = ++romFetchToken;
  romAbort?.abort();
  const controller = new AbortController();
  romAbort = controller;
  loadingRom.value = true;
  romFailed.value = false;
  selectedRom.value = null;
  try {
    const { data } = await romApi.getRom({
      romId,
      signal: controller.signal,
    });
    if (token === romFetchToken) selectedRom.value = data;
  } catch (error) {
    if (axios.isCancel(error) || controller.signal.aborted) return;
    if (token === romFetchToken) romFailed.value = true;
  } finally {
    if (token === romFetchToken) loadingRom.value = false;
  }
}

function selectAlbum(album: Album) {
  if (selectedRomId.value === album.romId && selectedRom.value) return;
  selectedRomId.value = album.romId;
  patchQuery(router, { game: String(album.romId) });
  void loadRom(album.romId);
}

function updateTrackFavorite(fileId: number, isFavorite: boolean) {
  // Mutate in place: replacing the arrays would invalidate every grouping
  // computed (albums, artists, genres, decades, platforms) for one flag.
  for (const list of [allTracks, tracks, freeRadioTracks]) {
    const hit = list.value.find((track) => track.rom_file_id === fileId);
    if (hit) hit.is_favorite = isFavorite;
  }
}

async function deleteSoundtrack(fileId: number, romId: number) {
  const catalogTrack = allTracks.value.find(
    (item) => item.rom_file_id === fileId,
  );
  const romTrack = (selectedRom.value?.files ?? []).find(
    (file) => file.id === fileId,
  );
  const name = romTrack?.file_name ?? catalogTrack?.title ?? "";
  const ok = await confirm({
    title: t("rom.delete-track-title"),
    body: name
      ? t("rom.delete-track-body-named", { name })
      : t("rom.delete-track-body"),
    confirmText: t("rom.soundtrack-delete-track"),
    tone: "danger",
  });
  if (!ok) return;

  try {
    await romApi.removeSoundtrack({ romId, fileId });
    tracks.value = tracks.value.filter((item) => item.rom_file_id !== fileId);
    allTracks.value = allTracks.value.filter(
      (item) => item.rom_file_id !== fileId,
    );
    freeRadioTracks.value = freeRadioTracks.value.filter(
      (item) => item.rom_file_id !== fileId,
    );

    if (selectedRom.value?.id === romId) {
      const currentAlbum = albums.value.find((album) => album.romId === romId);
      if (currentAlbum) {
        await loadRom(romId);
      } else {
        const nextAlbum = albums.value[0] ?? null;
        selectedRomId.value = nextAlbum?.romId ?? null;
        selectedRom.value = null;
        patchQuery(router, {
          game: nextAlbum ? String(nextAlbum.romId) : undefined,
        });
        if (nextAlbum) await loadRom(nextAlbum.romId);
      }
    }
    snackbar.success(t("rom.soundtrack-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.soundtrack-remove-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  }
}

async function fetchAllTracks() {
  loadingAllTracks.value = true;
  try {
    allTracks.value = await musicApi.getAllTracks();
    generateFreeRadio();
    const requestedArtist =
      typeof route.query.artist === "string" ? route.query.artist : "";
    selectedArtist.value =
      artists.value.find((artist) => artist.name === requestedArtist)?.name ??
      artists.value[0]?.name ??
      "";
    const requestedDecade = Number(route.query.decade);
    selectedDecade.value =
      decades.value.find((decade) => decade.startYear === requestedDecade)
        ?.startYear ??
      decades.value[0]?.startYear ??
      0;
    const requestedGenre =
      typeof route.query.genre === "string" ? route.query.genre : "";
    selectedGenre.value =
      genres.value.find((genre) => genre.name === requestedGenre)?.name ??
      genres.value[0]?.name ??
      "";
    const requestedPlatform = Number(route.query.platform);
    selectedPlatformId.value =
      platforms.value.find((platform) => platform.id === requestedPlatform)
        ?.id ??
      platforms.value[0]?.id ??
      0;
  } catch {
    allTracks.value = [];
  } finally {
    loadingAllTracks.value = false;
  }
}

function selectInitialAlbum() {
  const requested = Number(route.query.game);
  const next =
    albums.value.find((album) => album.romId === requested) ??
    albums.value[0] ??
    null;
  selectedRomId.value = next?.romId ?? null;
  if (next) void loadRom(next.romId);
  else selectedRom.value = null;
}

async function fetchAlbums() {
  const token = ++albumFetchToken;
  loadingAlbums.value = true;
  albumsFailed.value = false;
  try {
    const items = await musicApi.getAllTracks({ search: search.value.trim() });
    if (token !== albumFetchToken) return;
    tracks.value = items;

    selectInitialAlbum();
  } catch {
    if (token === albumFetchToken) albumsFailed.value = true;
  } finally {
    if (token === albumFetchToken) loadingAlbums.value = false;
  }
}

watch(mode, (value) => {
  patchQuery(router, {
    mode: value === "home" ? undefined : value,
    game:
      value === "album" && typeof route.query.game === "string"
        ? route.query.game
        : undefined,
    artist: value === "artist" ? selectedArtist.value || undefined : undefined,
    decade:
      value === "decade" && selectedDecade.value
        ? String(selectedDecade.value)
        : undefined,
    genre: value === "genre" ? selectedGenre.value || undefined : undefined,
    platform:
      value === "platform" && selectedPlatformId.value
        ? String(selectedPlatformId.value)
        : undefined,
  });
});

watch(
  () => route.query.mode,
  (value) => {
    const next = modeFromQuery(value);
    if (next !== mode.value) mode.value = next;
  },
);

watch(
  () => route.query.decade,
  (value) => {
    const requested = Number(value);
    if (
      requested &&
      requested !== selectedDecade.value &&
      decades.value.some((decade) => decade.startYear === requested)
    ) {
      selectedDecade.value = requested;
    }
  },
);

watch(
  () => route.query.genre,
  (value) => {
    if (
      typeof value === "string" &&
      value !== selectedGenre.value &&
      genres.value.some((genre) => genre.name === value)
    ) {
      selectedGenre.value = value;
    }
  },
);

watch(
  () => route.query.platform,
  (value) => {
    const requested = Number(value);
    if (
      requested &&
      requested !== selectedPlatformId.value &&
      platforms.value.some((platform) => platform.id === requested)
    ) {
      selectedPlatformId.value = requested;
    }
  },
);

watch(search, (value) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    patchQuery(router, { search: value.trim() || undefined, game: undefined });
    void fetchAlbums();
  }, 250);
});

watch(
  () => route.query.search,
  (value) => {
    const next = typeof value === "string" ? value : "";
    if (next !== search.value) search.value = next;
  },
);

onMounted(async () => {
  await fetchAllTracks();
  if (search.value.trim()) {
    await fetchAlbums();
    return;
  }
  tracks.value = [...allTracks.value];
  loadingAlbums.value = false;
  selectInitialAlbum();
});

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  romAbort?.abort();
});
</script>

<template>
  <section class="jukebox">
    <div class="jukebox__header">
      <PageHeader :title="t('common.jukebox')">
        <template #count>
          <RChip size="x-small" color="primary">{{ t("common.beta") }}</RChip>
        </template>
        <RBtn
          v-if="mode !== 'home'"
          class="jukebox__back"
          icon="mdi-arrow-left"
          variant="text"
          :tooltip="t('common.back')"
          :aria-label="t('common.back')"
          @click="openHome"
        />
      </PageHeader>
      <RDivider />
    </div>

    <main v-if="mode === 'home'" class="jukebox__home">
      <CardRow
        v-for="row in launchRows"
        :key="row.title"
        :title="row.title"
        gap="16px"
      >
        <RBtn
          v-for="tile in row.tiles"
          :key="tile.mode"
          class="jukebox__launch"
          variant="plain"
          @click="openMode(tile.mode)"
        >
          <span class="jukebox__launch-icon">
            <RIcon :icon="tile.icon" size="52" />
          </span>
          <strong>{{ tile.label }}</strong>
          <span class="jukebox__launch-count">{{ tile.count }}</span>
        </RBtn>
      </CardRow>
    </main>
    <aside v-if="mode === 'album'" class="jukebox__sidebar">
      <div class="jukebox__sidebar-head">
        <RTextField
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          :placeholder="t('common.search')"
          clearable
          hide-details
          density="compact"
        />
      </div>

      <div class="jukebox__albums r-v2-scroll-hidden">
        <template v-if="loadingAlbums">
          <RSkeletonBlock v-for="n in 7" :key="n" height="72px" rounded="md" />
        </template>
        <EmptyState
          v-else-if="albumsFailed"
          icon="mdi-music-note-off-outline"
          :message="t('common.unknown-error')"
        />
        <EmptyState
          v-else-if="!albums.length"
          icon="mdi-album"
          :message="t('common.no-results')"
        />
        <RList v-else density="default">
          <RListItem
            v-for="album in albums"
            :key="album.romId"
            :title="album.title"
            :subtitle="album.platform"
            :active="selectedRomId === album.romId"
            :aria-label="album.title"
            @click="selectAlbum(album)"
          >
            <template #prepend>
              <div class="jukebox__album-cover">
                <img
                  v-if="album.coverUrl"
                  :src="album.coverUrl"
                  alt=""
                  loading="lazy"
                />
                <RIcon v-else icon="mdi-album" size="22" />
              </div>
            </template>
            <template #append>
              <span class="jukebox__track-count">{{ album.trackCount }}</span>
            </template>
          </RListItem>
        </RList>
      </div>
    </aside>

    <aside v-if="mode === 'genre'" class="jukebox__sidebar">
      <div class="jukebox__albums r-v2-scroll-hidden">
        <EmptyState
          v-if="!genres.length"
          icon="mdi-shape"
          :message="t('common.no-results')"
        />
        <RList v-else density="default">
          <RListItem
            v-for="genre in genres"
            :key="genre.name"
            :title="genre.name"
            :active="selectedGenre === genre.name"
            @click="selectGenre(genre)"
          >
            <template #prepend>
              <div class="jukebox__artist-icon">
                <RIcon icon="mdi-shape" size="22" />
              </div>
            </template>
            <template #append>
              <span class="jukebox__track-count">{{
                genre.tracks.length
              }}</span>
            </template>
          </RListItem>
        </RList>
      </div>
    </aside>
    <main v-if="mode === 'genre'" class="jukebox__main">
      <SoundtrackPanel
        v-if="selectedGenreTracks.length"
        :key="selectedGenre"
        :music-tracks="selectedGenreTracks"
        :deletable="canEdit"
        class="jukebox__player"
        @delete-track="deleteSoundtrack"
        @favorite-track="updateTrackFavorite"
      />
      <EmptyState
        v-else
        variant="boxed"
        icon="mdi-shape"
        :message="t('common.no-results')"
      />
    </main>

    <aside v-if="mode === 'platform'" class="jukebox__sidebar">
      <div class="jukebox__albums r-v2-scroll-hidden">
        <EmptyState
          v-if="!platforms.length"
          icon="mdi-controller-classic"
          :message="t('common.no-results')"
        />
        <RList v-else density="default">
          <RListItem
            v-for="platform in platforms"
            :key="platform.id"
            :title="platform.name"
            :active="selectedPlatformId === platform.id"
            @click="selectPlatform(platform)"
          >
            <template #prepend>
              <div class="jukebox__platform-icon">
                <RPlatformIcon
                  :slug="platform.slug"
                  :alt="platform.name"
                  size="100%"
                  :show-tooltip="false"
                />
              </div>
            </template>
            <template #append>
              <span class="jukebox__track-count">{{
                platform.tracks.length
              }}</span>
            </template>
          </RListItem>
        </RList>
      </div>
    </aside>
    <main v-if="mode === 'platform'" class="jukebox__main">
      <SoundtrackPanel
        v-if="selectedPlatformTracks.length"
        :key="selectedPlatformId"
        :music-tracks="selectedPlatformTracks"
        :deletable="canEdit"
        class="jukebox__player"
        @delete-track="deleteSoundtrack"
        @favorite-track="updateTrackFavorite"
      />
      <EmptyState
        v-else
        variant="boxed"
        icon="mdi-controller-classic"
        :message="t('common.no-results')"
      />
    </main>

    <aside v-if="mode === 'decade'" class="jukebox__sidebar">
      <div class="jukebox__albums r-v2-scroll-hidden">
        <EmptyState
          v-if="!decades.length"
          icon="mdi-calendar-range"
          :message="t('common.no-results')"
        />
        <RList v-else density="default">
          <RListItem
            v-for="decade in decades"
            :key="decade.startYear"
            :title="decade.label"
            :active="selectedDecade === decade.startYear"
            :aria-label="decade.label"
            @click="selectDecade(decade)"
          >
            <template #prepend>
              <div class="jukebox__artist-icon">
                <RIcon icon="mdi-calendar-range" size="22" />
              </div>
            </template>
            <template #append>
              <span class="jukebox__track-count">{{
                decade.tracks.length
              }}</span>
            </template>
          </RListItem>
        </RList>
      </div>
    </aside>

    <main v-if="mode === 'decade'" class="jukebox__main">
      <SoundtrackPanel
        v-if="selectedDecadeTracks.length"
        :key="selectedDecade"
        :music-tracks="selectedDecadeTracks"
        :start-shuffled="true"
        :deletable="canEdit"
        class="jukebox__player"
        @delete-track="deleteSoundtrack"
        @favorite-track="updateTrackFavorite"
      />
      <EmptyState
        v-else
        variant="boxed"
        icon="mdi-calendar-range"
        :message="t('common.no-results')"
      />
    </main>

    <aside v-if="mode === 'artist'" class="jukebox__sidebar">
      <div class="jukebox__sidebar-head">
        <RTextField
          v-model="artistSearch"
          prepend-inner-icon="mdi-magnify"
          :placeholder="t('common.search')"
          clearable
          hide-details
          density="compact"
        />
      </div>
      <div class="jukebox__albums r-v2-scroll-hidden">
        <EmptyState
          v-if="!filteredArtists.length"
          icon="mdi-account-music"
          :message="t('common.no-results')"
        />
        <RList v-else density="default">
          <RListItem
            v-for="artist in filteredArtists"
            :key="artist.name"
            :title="artist.name"
            :active="selectedArtist === artist.name"
            :aria-label="artist.name"
            @click="selectArtist(artist)"
          >
            <template #prepend>
              <div class="jukebox__artist-icon">
                <RIcon icon="mdi-account-music" size="22" />
              </div>
            </template>
            <template #append>
              <span class="jukebox__track-count">{{
                artist.tracks.length
              }}</span>
            </template>
          </RListItem>
        </RList>
      </div>
    </aside>

    <main v-if="mode === 'artist'" class="jukebox__main">
      <SoundtrackPanel
        v-if="selectedArtistTracks.length"
        :key="selectedArtist"
        :music-tracks="selectedArtistTracks"
        :deletable="canEdit"
        class="jukebox__player"
        @delete-track="deleteSoundtrack"
        @favorite-track="updateTrackFavorite"
      />
      <EmptyState
        v-else
        variant="boxed"
        icon="mdi-account-music"
        :message="t('common.no-results')"
      />
    </main>

    <main v-if="mode === 'album'" class="jukebox__main">
      <div v-if="loadingRom" class="jukebox__player-loading">
        <RSkeletonBlock width="140px" height="140px" rounded="full" />
        <div class="jukebox__player-loading-body">
          <RSkeletonBlock width="30%" height="14px" />
          <RSkeletonBlock width="65%" height="28px" />
          <RSkeletonBlock width="45%" height="18px" />
        </div>
      </div>
      <EmptyState
        v-else-if="romFailed"
        variant="boxed"
        icon="mdi-music-note-off-outline"
        :message="t('common.unknown-error')"
      />
      <SoundtrackPanel
        v-else-if="selectedRom"
        :key="selectedRom.id"
        :rom="selectedRom"
        :deletable="canEdit"
        class="jukebox__player"
        @delete-track="deleteSoundtrack"
        @favorite-track="updateTrackFavorite"
      />
      <EmptyState
        v-else
        variant="boxed"
        icon="mdi-album"
        :message="t('common.no-results')"
      />
    </main>
    <template v-if="isSessionMode">
      <div v-if="loadingAllTracks" class="jukebox__play-all-loading">
        <RSkeletonBlock height="140px" rounded="md" />
      </div>
      <EmptyState
        v-else-if="!sessionTracks.length"
        class="jukebox__play-all"
        variant="boxed"
        icon="mdi-playlist-music"
        :message="t('common.no-results')"
      />
      <SoundtrackPanel
        v-else
        :key="mode"
        :music-tracks="sessionTracks"
        :deletable="canEdit"
        class="jukebox__play-all"
        @delete-track="deleteSoundtrack"
        @favorite-track="updateTrackFavorite"
      />
    </template>
  </section>
</template>

<style scoped>
.jukebox {
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}

.jukebox__header {
  grid-column: 1 / -1;
  padding: 24px var(--r-row-pad) 0;
}

.jukebox__back {
  margin-left: auto;
}

.jukebox__home {
  grid-column: 1 / -1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: var(--r-space-5) 0 60px;
}

.jukebox__launch {
  position: relative;
  --r-btn-rest-h: auto;
  width: 150px;
  flex: 0 0 150px;
  appearance: none;
  min-width: 0;
  padding: 14px 12px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition:
    background var(--r-motion-fast),
    border-color var(--r-motion-fast),
    transform var(--r-motion-fast);
}

.jukebox__launch :deep(.r-btn__content),
.jukebox__launch :deep(.r-btn__label) {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: inherit;
  white-space: normal;
}

html[data-input="mouse"] .jukebox__launch:hover,
html[data-input="touch"] .jukebox__launch:hover,
.jukebox__launch:focus-visible {
  background: var(--r-color-surface);
  border-color: var(--r-color-border-strong);
}

.jukebox__launch:focus-visible {
  border-color: var(--r-color-brand-primary);
  box-shadow:
    0 8px 28px color-mix(in srgb, black 35%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
  outline: none;
}

.jukebox__launch-icon {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  color: var(--r-color-fg-heading);
  opacity: 0.9;
  transition:
    opacity var(--r-motion-fast),
    transform var(--r-motion-fast);
}

html[data-input="mouse"] .jukebox__launch:hover .jukebox__launch-icon,
html[data-input="touch"] .jukebox__launch:hover .jukebox__launch-icon,
.jukebox__launch:focus-visible .jukebox__launch-icon {
  opacity: 1;
  transform: scale(1.05);
}

.jukebox__launch strong {
  min-height: 32px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.35;
  text-align: center;
}

.jukebox__launch-count {
  margin-top: auto;
  color: var(--r-color-fg-muted);
  font-size: 11px;
}

.jukebox__play-all {
  grid-column: 1 / -1;
  min-width: 0;
  min-height: 0;
}

.jukebox__play-all-loading {
  grid-column: 1 / -1;
  padding: var(--r-space-5);
}

.jukebox__sidebar {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--r-color-border);
  background: color-mix(in srgb, var(--r-color-bg-elevated) 70%, transparent);
}

.jukebox__sidebar-head {
  padding: 14px 16px;
  border-bottom: 1px solid var(--r-color-border);
}

.jukebox__albums {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.jukebox__album-cover {
  width: 42px;
  height: 56px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-cover-placeholder);
  color: var(--r-color-fg-muted);
}

.jukebox__artist-icon {
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: var(--r-radius-full);
  background: var(--r-color-cover-placeholder);
  color: var(--r-color-fg-muted);
}

.jukebox__platform-icon {
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  padding: 4px;
}

.jukebox__album-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.jukebox__track-count {
  min-width: 24px;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.jukebox__main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.jukebox__player {
  height: 100%;
}

.jukebox__player-loading {
  height: 100%;
  display: flex;
  align-items: flex-start;
  gap: var(--r-space-5);
  padding: var(--r-space-5);
}

.jukebox__player-loading-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding-top: var(--r-space-4);
}

html[data-bp~="sm-and-down"] .jukebox {
  grid-template-columns: minmax(210px, 36vw) minmax(0, 1fr);
}

html[data-bp~="xs"] .jukebox {
  height: calc(100dvh - var(--r-nav-h) - var(--r-bottom-nav-h));
  grid-template-columns: 76px minmax(0, 1fr);
}

html[data-bp~="xs"] .jukebox__home {
  padding: var(--r-space-4) 0 40px;
}

html[data-bp~="xs"] .jukebox__launch {
  width: 110px;
  flex-basis: 110px;
  padding: 8px;
  gap: 4px;
}

html[data-bp~="xs"] .jukebox__launch-icon {
  width: 52px;
  height: 52px;
}

html[data-bp~="xs"] .jukebox__launch strong {
  min-height: 28px;
  font-size: 10px;
}

html[data-bp~="xs"] .jukebox__launch-count {
  font-size: 9px;
}

html[data-bp~="xs"] .jukebox__sidebar-head {
  display: none;
}

html[data-bp~="xs"] .jukebox__albums {
  padding: 8px;
}

html[data-bp~="xs"] .jukebox__albums :deep(.r-list-item) {
  justify-content: center;
  padding: 6px;
}

html[data-bp~="xs"] .jukebox__albums :deep(.r-list-item__body),
html[data-bp~="xs"] .jukebox__albums :deep(.r-list-item__append) {
  display: none;
}

html[data-bp~="xs"] .jukebox__player :deep(.r-v2-stp__row-duration),
html[data-bp~="xs"] .jukebox__player :deep(.r-v2-stp__row-size) {
  display: none;
}

html[data-bp~="xs"] .jukebox__player-loading {
  flex-direction: column;
}
</style>
