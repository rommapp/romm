<script setup lang="ts">
// Soundtrack Panel: renders the shared `useSoundtrackPlayer` queue. The
// HTMLAudioElement lives in MiniPlayer, which hides while this panel is on
// screen so only one "now playing" surface exists at a time.
import {
  RBtn,
  RChip,
  RIcon,
  RSkeletonBlock,
  RSlider,
  RSpinner,
  RVirtualScroller,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, defineAsyncComponent, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { TrackMetaSchema } from "@/__generated__";
import useMusicFavorites from "@/stores/musicFavorites";
import useSoundtrackPlayer, {
  type PlayerMeta,
  type PlayerTrack,
} from "@/stores/soundtrackPlayer";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import type { PanelTrack } from "@/v2/utils/soundtrackTracks";
import { formatTrackTime } from "@/v2/utils/time";
import TrackRow from "./TrackRow.vue";

// Row height must match `.r-v2-stp__row` in TrackRow's stylesheet.
const ROW_HEIGHT = 52;

// The shared store owns volume / muted state so the same widget can sit in
// the mini-player too.
const VolumeControl = defineAsyncComponent(
  () => import("@/v2/components/Soundtrack/VolumeControl.vue"),
);

const props = defineProps<{
  tracks: PanelTrack[];
  /** Identifies the queue so the store can tell one playlist from another. */
  playlistKey?: number | null;
  loading?: boolean;
  /** True while the next page is in flight, for the queue header spinner. */
  loadingMore?: boolean;
  /** Size of the whole queue when `tracks` is only the loaded window. */
  totalTracks?: number;
  startShuffled?: boolean;
  /** Cover shown when the active track has no art of its own. */
  fallbackArtUrl?: string;
  /** Show the per-track delete button (host gates it on the ROM write grant). */
  deletable?: boolean;
  /** Opt into the now-playing-rail layout when the container is wide enough. */
  wide?: boolean;
  /** Icon for the empty-queue state (defaults to a generic playlist glyph). */
  emptyIcon?: string;
}>();
const emit = defineEmits<{
  (e: "delete-track", fileId: number, romId: number): void;
  /** The furthest track index the viewer or playback has reached, so the
   *  host can page in more before the list or the queue runs out. */
  (e: "reached", index: number): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const favorites = useMusicFavorites();
const canEditPlaylists = useCan("playlist.edit");

const player = useSoundtrackPlayer();
const {
  track: activeStoreTrack,
  isPlaying,
  isBuffering,
  currentTime,
  duration,
  playlist,
  hasPrevious,
  hasNext,
  isShuffled,
} = storeToRefs(player);

const tracks = computed(() => props.tracks);

function trackKey(romId: number, fileId: number): string {
  return `${romId}:${fileId}`;
}

// The list follows the store's queue so what you see is what plays next.
const displayedTracks = computed(() => {
  if (!isShuffled.value) return tracks.value;
  const byKey = new Map(
    tracks.value.map((track) => [trackKey(track.romId, track.id), track]),
  );
  const ordered = playlist.value
    .map((entry) => byKey.get(trackKey(entry.romId, entry.fileId)))
    .filter((track): track is PanelTrack => Boolean(track));
  return ordered.length === tracks.value.length ? ordered : tracks.value;
});

let shouldStartShuffled = Boolean(props.startShuffled);

function toPlayerMeta(track: PanelTrack): PlayerMeta {
  const m = track.meta;
  return {
    title: m?.title ?? track.title,
    artist: m?.artist ?? undefined,
    album: m?.album ?? undefined,
    genre: m?.genre ?? undefined,
    year: m?.year ?? undefined,
    track: m?.track ?? undefined,
    disc: m?.disc ?? undefined,
    duration: track.durationSeconds,
    coverUrl: track.coverUrl,
    folderCoverUrl: props.fallbackArtUrl,
    gameArtworkUrl: track.gameArtworkUrl ?? props.fallbackArtUrl,
  };
}

function buildPlayerPayload(): {
  playerTracks: PlayerTrack[];
  metas: Record<number, PlayerMeta>;
} {
  const playerTracks: PlayerTrack[] = [];
  const metas: Record<number, PlayerMeta> = {};
  for (const track of tracks.value) {
    playerTracks.push({
      romId: track.romId,
      fileId: track.id,
      fileName: track.fileName,
      url: track.url,
    });
    metas[track.id] = toPlayerMeta(track);
  }
  return { playerTracks, metas };
}

const activeTrackId = computed(() => {
  const active = activeStoreTrack.value;
  if (!active) return null;
  return tracks.value.some(
    (track) => track.id === active.fileId && track.romId === active.romId,
  )
    ? active.fileId
    : null;
});

const activeTrack = computed(() =>
  tracks.value.find((track) => track.id === activeTrackId.value),
);

const activeMeta = computed<TrackMetaSchema | undefined>(
  () => activeTrack.value?.meta,
);

const activeArtUrl = computed(
  () =>
    activeTrack.value?.coverUrl ??
    activeTrack.value?.gameArtworkUrl ??
    props.fallbackArtUrl ??
    null,
);

const activeTitle = computed(() => activeTrack.value?.title ?? "");

function onViewportRange(range: { first: number; last: number }) {
  emit("reached", range.last);
}

watch(activeTrackId, (fileId) => {
  if (fileId == null) return;
  const index = displayedTracks.value.findIndex((track) => track.id === fileId);
  if (index >= 0) emit("reached", index);
});

const panelRoot = ref<HTMLElement | null>(null);
watch(activeTrackId, async (fileId, previousFileId) => {
  if (fileId == null || fileId === previousFileId) return;
  await nextTick();
  panelRoot.value
    ?.querySelector<HTMLElement>(`[data-track-id="${fileId}"]`)
    ?.scrollIntoView({ block: "nearest" });
});

// Chips shown in the now-playing header. The artist is not repeated here
// because it has its own line right above.
type ChipItem = { icon: string; label: string; color?: string };

function headerChips(meta: TrackMetaSchema | undefined): ChipItem[] {
  if (!meta) return [];
  const items: ChipItem[] = [];
  if (meta.album) items.push({ icon: "mdi-album", label: meta.album });
  if (meta.year)
    items.push({
      icon: "mdi-calendar",
      label: String(meta.year),
      color: "accent",
    });
  if (meta.genre)
    items.push({ icon: "mdi-music-clef-treble", label: meta.genre });
  if (meta.track)
    items.push({
      icon: "mdi-numeric",
      label: t("rom.chip-track-n", { n: meta.track }),
    });
  if (meta.disc)
    items.push({
      icon: "mdi-disc",
      label: t("rom.chip-disc-n", { n: meta.disc }),
    });
  return items;
}

const totalDurationSeconds = computed(() =>
  tracks.value.reduce(
    (total, track) => total + (track.durationSeconds ?? 0),
    0,
  ),
);

const trackCount = computed(() => props.totalTracks ?? tracks.value.length);

// Only the loaded window has durations, so the running time is withheld until
// the whole queue is in rather than reported as a total it is not.
const isFullyLoaded = computed(() => trackCount.value === tracks.value.length);

const queueSummary = computed(() => {
  if (isFullyLoaded.value && totalDurationSeconds.value > 0)
    return t("rom.tracks-summary", {
      count: trackCount.value.toLocaleString(),
      duration: formatTrackTime(totalDurationSeconds.value),
    });
  return t("rom.tracks-n", trackCount.value, {
    named: { n: trackCount.value.toLocaleString() },
  });
});

// Reloading the queue whenever the input list changes keeps "next" pointing at
// what the panel is showing, without the host having to drive the store.
watch(
  tracks,
  (next) => {
    if (next.length === 0) return;
    const active = activeStoreTrack.value;
    const stillListed =
      active &&
      next.some(
        (track) => track.id === active.fileId && track.romId === active.romId,
      );
    const { playerTracks, metas } = buildPlayerPayload();
    player.loadPlaylist(playerTracks, metas, props.playlistKey ?? null, true);
    if (shouldStartShuffled) {
      if (!isShuffled.value) player.toggleShuffle();
      shouldStartShuffled = false;
    }
    if (!stillListed && !active) return;
  },
  { immediate: true },
);

function selectTrack(fileId: number) {
  // Clicking the row that is already loaded toggles it instead of restarting.
  if (fileId === activeTrackId.value) {
    player.togglePlayPause();
    return;
  }
  if (!tracks.value.some((track) => track.id === fileId)) return;
  const { playerTracks, metas } = buildPlayerPayload();
  player.loadPlaylist(
    playerTracks,
    metas,
    props.playlistKey ?? null,
    isShuffled.value,
  );
  const entry = playerTracks.find((p) => p.fileId === fileId);
  if (!entry) return;
  player.play(entry, metas[fileId]);
  if (shouldStartShuffled && !isShuffled.value) player.toggleShuffle();
  shouldStartShuffled = false;
}

function onDelete(track: PanelTrack) {
  if (activeTrackId.value === track.id) player.stop();
  emit("delete-track", track.id, track.romId);
}

async function onToggleFavorite(track: PanelTrack) {
  const next = await favorites.toggle(track.id);
  if (next === null) {
    snackbar.error(t("common.soundtrack-favorite-failed"), {
      icon: "mdi-alert-circle-outline",
    });
    return;
  }
  snackbar.success(
    t(
      next
        ? "common.soundtrack-favorite-added"
        : "common.soundtrack-favorite-removed",
    ),
    { icon: next ? "mdi-heart" : "mdi-heart-outline" },
  );
}

// An anchor click routes the download with the original filename instead
// of opening the file in a new tab.
function downloadTrack(track: PanelTrack) {
  const a = document.createElement("a");
  a.href = track.url;
  a.download = track.fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function seekValueText(v: number): string {
  return t("rom.seek-progress", {
    current: formatTrackTime(v),
    duration: formatTrackTime(duration.value),
  });
}
</script>

<template>
  <div ref="panelRoot" class="r-v2-stp-host">
    <div class="r-v2-stp" :class="{ 'r-v2-stp--wide': wide }">
      <!-- Blurred echo of the active art behind the whole surface. -->
      <div
        v-if="activeArtUrl"
        class="r-v2-stp__ambient"
        :style="{ backgroundImage: `url(${activeArtUrl})` }"
        aria-hidden="true"
      />

      <!-- Now playing rail (wide) / header (stacked) -->
      <aside class="r-v2-stp__hero">
        <div class="r-v2-stp__stage">
          <div
            class="r-v2-stp__vinyl"
            :class="{
              'r-v2-stp__vinyl--out': activeTrack,
              'r-v2-stp__vinyl--spinning': activeTrack && isPlaying,
            }"
            aria-hidden="true"
          >
            <img
              v-if="activeArtUrl"
              :src="activeArtUrl"
              class="r-v2-stp__vinyl-label"
              alt=""
            />
          </div>
          <div class="r-v2-stp__art">
            <img
              v-if="activeArtUrl"
              :src="activeArtUrl"
              class="r-v2-stp__art-img"
              alt=""
            />
            <RIcon v-else icon="mdi-music-note" size="44" />
            <div
              v-if="activeTrack && isBuffering"
              class="r-v2-stp__buffering"
              aria-hidden="true"
            >
              <RSpinner :size="28" :width="3" color="white" />
            </div>
          </div>
        </div>

        <div class="r-v2-stp__now-body">
          <div class="r-v2-stp__now-eyebrow">
            <span v-if="loading">
              <RSpinner :size="14" />
              {{ t("rom.loading-metadata") }}
            </span>
            <span v-else-if="activeTrack" class="r-v2-stp__now-state">
              {{ isPlaying ? t("rom.now-playing") : t("rom.paused") }}
            </span>
            <span v-else>
              {{ t("rom.tracks-n", trackCount, { named: { n: trackCount } }) }}
            </span>
          </div>
          <h3 class="r-v2-stp__now-title">
            {{ activeTrack ? activeTitle : t("rom.pick-track-prompt") }}
          </h3>
          <div v-if="activeMeta?.artist" class="r-v2-stp__now-artist">
            {{ activeMeta.artist }}
          </div>
          <div v-if="activeMeta" class="r-v2-stp__chips">
            <RChip
              v-for="(c, i) in headerChips(activeMeta)"
              :key="`h-${i}`"
              size="small"
              variant="translucent"
              :color="c.color"
              :prepend-icon="c.icon"
            >
              {{ c.label }}
            </RChip>
          </div>
          <div v-else-if="!activeTrack" class="r-v2-stp__now-hint">
            {{ t("rom.soundtrack-placeholder-hint") }}
          </div>
        </div>

        <!-- Transport: always rendered so the surface keeps its vocabulary
             even before the user picks a track. Buttons that can't act
             without a track go disabled; the volume slider stays live
             because it controls the shared mute / level regardless. -->
        <div
          class="r-v2-stp__controls"
          role="region"
          :aria-label="t('rom.soundtrack-player')"
        >
          <div class="r-v2-stp__transport">
            <RBtn
              icon="mdi-shuffle"
              :variant="isShuffled ? 'translucent' : 'text'"
              size="small"
              :disabled="tracks.length === 0"
              :color="isShuffled ? 'primary' : undefined"
              :aria-pressed="isShuffled"
              :tooltip="t('common.shuffle')"
              :aria-label="t('common.shuffle')"
              @click="player.toggleShuffle()"
            />
            <RBtn
              icon="mdi-skip-previous"
              variant="text"
              size="small"
              :disabled="!hasPrevious"
              :tooltip="t('rom.soundtrack-previous')"
              :aria-label="t('rom.soundtrack-previous')"
              @click="player.previous()"
            />
            <RBtn
              :icon="isPlaying ? 'mdi-pause' : 'mdi-play'"
              variant="flat"
              color="primary"
              class="r-v2-stp__play"
              :disabled="!activeTrack"
              :tooltip="
                isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
              "
              :aria-label="
                isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
              "
              @click="player.togglePlayPause()"
            />
            <RBtn
              icon="mdi-skip-next"
              variant="text"
              size="small"
              :disabled="!hasNext"
              :tooltip="t('rom.soundtrack-next')"
              :aria-label="t('rom.soundtrack-next')"
              @click="player.next()"
            />
            <VolumeControl size="small" />
          </div>
          <div class="r-v2-stp__timeline">
            <span class="r-v2-stp__time">{{
              formatTrackTime(currentTime)
            }}</span>
            <RSlider
              :model-value="currentTime"
              :max="duration || 0"
              :step="0.1"
              :disabled="!activeTrack"
              color="primary"
              class="r-v2-stp__slider"
              :aria-label="t('rom.soundtrack-seek')"
              :aria-valuetext="seekValueText(currentTime)"
              @update:model-value="(v: number) => player.seek(v)"
            />
            <span class="r-v2-stp__time r-v2-stp__time--right">
              {{ formatTrackTime(duration) }}
            </span>
          </div>
        </div>
      </aside>

      <!-- Queue -->
      <section class="r-v2-stp__queue">
        <header class="r-v2-stp__queue-head">
          <span v-if="trackCount > 0" class="r-v2-stp__queue-count">
            {{ queueSummary }}
          </span>
          <span v-if="loadingMore" class="r-v2-stp__queue-more">
            <RSpinner :size="12" :width="2" />
            {{ t("common.loading") }}
          </span>
        </header>

        <div v-if="loading" class="r-v2-stp__queue-skeleton">
          <RSkeletonBlock v-for="n in 8" :key="n" height="48px" rounded="md" />
        </div>
        <RVirtualScroller
          v-else-if="displayedTracks.length"
          class="r-v2-stp__list"
          :items="displayedTracks"
          :get-item-height="() => ROW_HEIGHT"
          :get-item-key="(item: unknown) => (item as PanelTrack).id"
          @update:viewport-range="onViewportRange"
        >
          <template #default="{ item, index }">
            <TrackRow
              :track="item as PanelTrack"
              :index="index"
              :active="activeTrackId === (item as PanelTrack).id"
              :playing="
                activeTrackId === (item as PanelTrack).id &&
                isPlaying &&
                !isBuffering
              "
              :buffering="
                activeTrackId === (item as PanelTrack).id && isBuffering
              "
              :deletable="deletable"
              :favoritable="canEditPlaylists"
              @select="selectTrack"
              @download="downloadTrack"
              @delete="onDelete"
              @toggle-favorite="onToggleFavorite"
            />
          </template>
        </RVirtualScroller>
        <!-- Empty queue keeps the player chrome on screen; only the list
             area says there is nothing to play. -->
        <div v-else class="r-v2-stp__queue-empty">
          <EmptyState
            variant="boxed"
            :icon="emptyIcon ?? 'mdi-playlist-music'"
            :message="t('common.no-results')"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.r-v2-stp-host {
  height: 100%;
  min-height: 0;
  container-type: inline-size;
}

.r-v2-stp {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding: var(--r-space-4);
  height: 100%;
  min-height: 0;
  overflow: hidden;
  isolation: isolate;
}

/* Ambient backdrop: the active art, blown up and blurred. Scaled past the
   edges so the blur never shows a hard boundary; masked so it fades before
   reaching the queue's lower half. */
.r-v2-stp__ambient {
  position: absolute;
  inset: 0;
  z-index: -1;
  background-size: cover;
  background-position: center 30%;
  transform: scale(1.3);
  filter: blur(72px) saturate(1.4);
  opacity: 0.2;
  mask-image: linear-gradient(to bottom, black 0%, transparent 85%);
  pointer-events: none;
}

/* Hero: stacked layout by default: art + text side by side, transport
   strip underneath spanning the full width. */
.r-v2-stp__hero {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas:
    "stage body"
    "controls controls";
  gap: var(--r-space-3) var(--r-space-4);
  align-items: center;
}

/* Stage: the square art with the vinyl tucked behind it. */
.r-v2-stp__stage {
  grid-area: stage;
  position: relative;
  width: 108px;
  height: 108px;
}

.r-v2-stp__art {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: var(--r-radius-md);
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--r-color-cover-placeholder);
  color: var(--r-color-fg-muted);
  border: 1px solid var(--r-color-border);
  box-shadow: 0 10px 30px color-mix(in srgb, black 35%, transparent);
  z-index: 1;
}

.r-v2-stp__art-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

/* Vinyl: pure CSS record that slides out from behind the art when a track
   is loaded and rotates while it plays. Hidden in the stacked layout where
   there is no room for the reveal. */
.r-v2-stp__vinyl {
  display: none;
  position: absolute;
  top: 50%;
  left: 0;
  width: 92%;
  aspect-ratio: 1;
  border-radius: var(--r-radius-full);
  /* Individual transform properties: `translate` composes before `rotate`,
     so the slide-out offset stays fixed while the spin turns in place. */
  translate: 2% -50%;
  transition:
    translate var(--r-motion-slow) var(--r-motion-ease-out),
    opacity var(--r-motion-slow) var(--r-motion-ease-out);
  opacity: 0;
  /* Grooves: a near-black disc, fine repeating rings, and a soft light
     sweep so it reads as pressed vinyl rather than a flat circle. */
  background:
    conic-gradient(
      from 210deg,
      transparent 0 12%,
      color-mix(in srgb, white 7%, transparent) 16%,
      transparent 20% 60%,
      color-mix(in srgb, white 5%, transparent) 65%,
      transparent 70%
    ),
    repeating-radial-gradient(
      circle at 50% 50%,
      color-mix(in srgb, white 6%, transparent) 0 1px,
      transparent 1px 4px
    ),
    radial-gradient(
      circle at 50% 50%,
      color-mix(in srgb, black 82%, white) 0 99%,
      transparent 100%
    );
  /* The rim ring keeps the disc legible against a near-black page. */
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, white 14%, transparent),
    0 6px 22px color-mix(in srgb, black 45%, transparent);
}

.r-v2-stp__vinyl-label {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 38%;
  height: 38%;
  transform: translate(-50%, -50%);
  border-radius: var(--r-radius-full);
  object-fit: cover;
  box-shadow: 0 0 0 2px color-mix(in srgb, black 60%, transparent);
}

/* Spindle hole on top of the label. */
.r-v2-stp__vinyl::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 7%;
  height: 7%;
  transform: translate(-50%, -50%);
  border-radius: var(--r-radius-full);
  background: var(--r-color-bg);
  box-shadow: inset 0 0 0 2px color-mix(in srgb, black 50%, transparent);
}

.r-v2-stp__vinyl--out {
  opacity: 1;
  translate: 34% -50%;
}

@keyframes r-v2-stp-vinyl-spin {
  from {
    rotate: 0deg;
  }
  to {
    rotate: 360deg;
  }
}

.r-v2-stp__vinyl--spinning {
  animation: r-v2-stp-vinyl-spin 6s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .r-v2-stp__vinyl--spinning {
    animation: none;
  }
}

.r-v2-stp__buffering {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 45%, transparent);
  z-index: 2;
}

.r-v2-stp__now-body {
  grid-area: body;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-v2-stp__now-eyebrow {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.r-v2-stp__now-state {
  color: var(--r-color-brand-primary);
}

.r-v2-stp__now-title {
  margin: 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-semibold);
  line-height: var(--r-line-height-tight);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.r-v2-stp__now-artist {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-md);
}

.r-v2-stp__chips {
  display: flex;
  flex-wrap: nowrap;
  gap: var(--r-space-1);
  margin-top: var(--r-space-1);
  overflow: hidden;
}

.r-v2-stp__now-hint {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
  max-width: 420px;
}

/* Controls: one strip in the stacked layout, a column in the rail. */
.r-v2-stp__controls {
  grid-area: controls;
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
}

.r-v2-stp__transport {
  display: flex;
  align-items: center;
  gap: var(--r-space-1);
}

.r-v2-stp__play {
  border-radius: var(--r-radius-full);
}

.r-v2-stp__timeline {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
}

.r-v2-stp__slider {
  flex: 1;
}

.r-v2-stp__time {
  font-variant-numeric: tabular-nums;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  min-width: 40px;
}

.r-v2-stp__time--right {
  text-align: right;
}

/* Queue */
.r-v2-stp__queue {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-v2-stp__queue-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 18px;
  padding: 0 var(--r-space-2);
}

.r-v2-stp__queue-count {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.r-v2-stp__queue-more {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-2);
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
}

.r-v2-stp__queue-empty {
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  align-content: center;
}

.r-v2-stp__queue-empty > * {
  min-width: min(320px, 100%);
}

.r-v2-stp__queue-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

.r-v2-stp__list {
  flex: 1;
  min-height: 0;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}

.r-v2-stp__list::-webkit-scrollbar {
  width: 4px;
}

.r-v2-stp__list::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 2px;
}

/* Wide layout: now-playing rail on the left, queue on the right. Only
   engages when the host opted in AND the container has the room. */
@container (min-width: 860px) {
  .r-v2-stp--wide {
    display: grid;
    grid-template-columns: 340px minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr);
    gap: var(--r-space-6);
    padding: var(--r-space-5) var(--r-space-6);
  }

  .r-v2-stp--wide .r-v2-stp__hero {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "stage"
      "body"
      "controls";
    align-content: start;
    align-items: start;
    gap: var(--r-space-5);
    min-height: 0;
    overflow: hidden auto;
    padding: var(--r-space-2);
  }

  /* Room on the right for the vinyl to slide into. */
  .r-v2-stp--wide .r-v2-stp__stage {
    width: 236px;
    height: 236px;
    margin-right: 72px;
  }

  .r-v2-stp--wide .r-v2-stp__art {
    border-radius: var(--r-radius-lg);
  }

  .r-v2-stp--wide .r-v2-stp__vinyl {
    display: block;
  }

  .r-v2-stp--wide .r-v2-stp__now-title {
    font-size: var(--r-font-size-2xl);
    -webkit-line-clamp: 3;
    line-clamp: 3;
  }

  .r-v2-stp--wide .r-v2-stp__chips {
    flex-wrap: wrap;
    overflow: visible;
  }

  .r-v2-stp--wide .r-v2-stp__controls {
    flex-direction: column;
    align-items: stretch;
    gap: var(--r-space-2);
  }

  .r-v2-stp--wide .r-v2-stp__transport {
    justify-content: center;
    gap: var(--r-space-2);
  }

  .r-v2-stp--wide .r-v2-stp__queue {
    padding-top: var(--r-space-2);
  }
}

html[data-bp~="xs"] .r-v2-stp {
  padding: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-stp__stage {
  width: 72px;
  height: 72px;
}

html[data-bp~="xs"] .r-v2-stp__controls {
  flex-wrap: wrap;
  gap: var(--r-space-2);
}

html[data-bp~="xs"] .r-v2-stp__timeline {
  order: 2;
  flex: 1 0 100%;
}
</style>
