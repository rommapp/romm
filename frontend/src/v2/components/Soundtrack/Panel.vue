<script setup lang="ts">
// Soundtrack Panel — v2 embedded soundtrack player.
//
// Consumes the shared `useSoundtrackPlayer` store (the actual HTMLAudioElement
// lives inside MiniPlayer, which stays mounted app-wide). Clicking a track
// here fills the store playlist and calls `player.play(...)`; the mini-player
// hides automatically whenever this panel is hosted by a full soundtrack
// surface, so only one "now playing" surface is ever on screen.
//
// Input is always a normalized `PanelTrack[]`; the two sources (a ROM's own
// files, the music catalog) do their mapping in `utils/soundtrackTracks`.
import {
  RBtn,
  RChip,
  RIcon,
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
import { formatBytes } from "@/utils";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import type { PanelTrack } from "@/v2/utils/soundtrackTracks";
import TrackRow from "./TrackRow.vue";

// Row height must match `.r-v2-stp__row` in the stylesheet below.
const ROW_HEIGHT = 52;

// Volume / mute widget — v2 native (RMenu + RSlider + RBtn). The
// shared `useSoundtrackPlayer` store owns the volume / muted state so
// the same widget can sit in the mini-player too without needing a
// local model.
const VolumeControl = defineAsyncComponent(
  () => import("@/v2/components/Soundtrack/VolumeControl.vue"),
);

const props = defineProps<{
  tracks: PanelTrack[];
  /** Identifies the queue so the store can tell one playlist from another. */
  playlistKey?: number | null;
  loading?: boolean;
  /** True while the next page is in flight, for the list's footer spinner. */
  loadingMore?: boolean;
  /** Size of the whole queue when `tracks` is only the loaded window. */
  totalTracks?: number;
  startShuffled?: boolean;
  /** Cover shown when the active track has no art of its own. */
  fallbackArtUrl?: string;
  /** Show the per-track delete button (host gates it on the ROM write grant). */
  deletable?: boolean;
  uploadable?: boolean;
}>();
const emit = defineEmits<{
  (e: "upload-tracks"): void;
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

// Chips shown in the now-playing header.
type ChipItem = { icon: string; label: string; color?: string };

function headerChips(meta: TrackMetaSchema | undefined): ChipItem[] {
  if (!meta) return [];
  const items: ChipItem[] = [];
  if (meta.album) items.push({ icon: "mdi-album", label: meta.album });
  if (meta.artist)
    items.push({ icon: "mdi-account-music", label: meta.artist });
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

// Mirror the saves/states pattern: synthesize an anchor click against
// the file content endpoint so the browser routes the download with
// the original filename instead of opening it in a new tab.
function downloadTrack(track: PanelTrack) {
  const a = document.createElement("a");
  a.href = track.url;
  a.download = track.fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function fmt(s: number | undefined | null) {
  if (s == null || !Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${sec}`;
}

function seekValueText(v: number): string {
  return t("rom.seek-progress", {
    current: fmt(v),
    duration: fmt(duration.value),
  });
}
</script>

<template>
  <div ref="panelRoot" class="r-v2-stp">
    <!-- Now playing / placeholder header -->
    <header class="r-v2-stp__now">
      <div class="r-v2-stp__cover">
        <div
          v-if="activeArtUrl"
          class="r-v2-stp__cover-rotor"
          :class="{
            'r-v2-stp__cover-rotor--spinning': activeTrack && isPlaying,
          }"
        >
          <img :src="activeArtUrl" class="r-v2-stp__cover-img" alt="" />
        </div>
        <RIcon v-else icon="mdi-music-note" size="48" />
        <div
          v-if="activeTrack && isBuffering"
          class="r-v2-stp__buffering"
          aria-hidden="true"
        >
          <RSpinner :size="28" :width="3" color="white" />
        </div>
      </div>

      <div class="r-v2-stp__now-body">
        <div class="r-v2-stp__now-eyebrow">
          <span v-if="loading">
            <RSpinner :size="14" />
            {{ t("rom.loading-metadata") }}
          </span>
          <span v-else-if="activeTrack">
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
    </header>

    <!-- Transport controls — always rendered so the surface keeps its
         vocabulary even before the user picks a track. Buttons that
         can't act without a track go disabled; the volume slider stays
         live because it controls the shared mute / level regardless. -->
    <div
      class="r-v2-stp__controls"
      role="region"
      :aria-label="t('rom.soundtrack-player')"
    >
      <div class="r-v2-stp__transport">
        <RBtn
          variant="text"
          size="small"
          :disabled="!hasPrevious"
          prepend-icon="mdi-skip-previous"
          :tooltip="t('rom.soundtrack-previous')"
          :aria-label="t('rom.soundtrack-previous')"
          @click="player.previous()"
        />
        <RBtn
          variant="text"
          size="small"
          :disabled="!activeTrack"
          :prepend-icon="isPlaying ? 'mdi-pause-circle' : 'mdi-play-circle'"
          :tooltip="
            isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
          "
          :aria-label="
            isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
          "
          @click="player.togglePlayPause()"
        />
        <RBtn
          variant="text"
          size="small"
          :disabled="!hasNext"
          prepend-icon="mdi-skip-next"
          :tooltip="t('rom.soundtrack-next')"
          :aria-label="t('rom.soundtrack-next')"
          @click="player.next()"
        />
      </div>
      <div class="r-v2-stp__timeline">
        <span class="r-v2-stp__time">{{ fmt(currentTime) }}</span>
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
          {{ fmt(duration) }}
        </span>
      </div>
      <div class="r-v2-stp__volume">
        <VolumeControl size="small" />
      </div>
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
    </div>

    <!-- Track list. Virtualised: the jukebox's play-all mode hands this the
         whole library, and each row owns a menu. -->
    <RVirtualScroller
      v-if="displayedTracks.length"
      class="r-v2-stp__list"
      :items="displayedTracks"
      :get-item-height="() => ROW_HEIGHT"
      :get-item-key="(item: unknown) => (item as PanelTrack).id"
      @update:viewport-range="onViewportRange"
    >
      <template #default="{ item }">
        <TrackRow
          :track="item as PanelTrack"
          :active="activeTrackId === (item as PanelTrack).id"
          :playing="
            activeTrackId === (item as PanelTrack).id &&
            isPlaying &&
            !isBuffering
          "
          :buffering="activeTrackId === (item as PanelTrack).id && isBuffering"
          :deletable="deletable"
          :favoritable="canEditPlaylists"
          @select="selectTrack"
          @download="downloadTrack"
          @delete="onDelete"
          @toggle-favorite="onToggleFavorite"
        />
      </template>
    </RVirtualScroller>

    <!-- Footer -->
    <footer class="r-v2-stp__footer">
      <span
        v-if="isFullyLoaded && totalDurationSeconds > 0"
        class="r-v2-stp__footer-total"
      >
        {{
          t("rom.tracks-summary", {
            count: trackCount,
            duration: fmt(totalDurationSeconds),
          })
        }}
      </span>
      <span v-else-if="trackCount > 0" class="r-v2-stp__footer-total">
        {{ t("rom.tracks-n", trackCount, { named: { n: trackCount } }) }}
      </span>
      <span v-if="loadingMore" class="r-v2-stp__footer-more">
        <RSpinner :size="12" :width="2" />
        {{ t("common.loading") }}
      </span>
    </footer>
  </div>
</template>

<style scoped>
.r-v2-stp {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  padding: var(--r-space-4);
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* Now playing / placeholder header */
.r-v2-stp__now {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: var(--r-space-4);
  align-items: center;
}

.r-v2-stp__cover {
  position: relative;
  width: 140px;
  height: 140px;
  border-radius: var(--r-radius-full);
  overflow: hidden;
  background: linear-gradient(
    135deg,
    var(--r-color-surface),
    var(--r-color-bg)
  );
  border: 1px solid var(--r-color-border);
  display: grid;
  place-items: center;
  box-shadow:
    0 8px 24px color-mix(in srgb, black 35%, transparent),
    0 0 0 4px color-mix(in srgb, black 20%, transparent);
}

.r-v2-stp__cover-rotor {
  position: absolute;
  inset: 0;
  transform-origin: 50% 50%;
  transform-box: border-box;
  animation: r-v2-stp-spin 12s linear infinite;
  animation-play-state: paused;
}

.r-v2-stp__cover-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

.r-v2-stp__cover-rotor--spinning {
  animation-play-state: running;
}

.r-v2-stp__cover::after {
  content: "";
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--r-color-bg);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  box-shadow: inset 0 0 0 2px color-mix(in srgb, black 50%, transparent);
}

.r-v2-stp__buffering {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 45%, transparent);
  z-index: 3;
}

@media (prefers-reduced-motion: reduce) {
  .r-v2-stp__cover-rotor {
    animation: none;
  }
}

.r-v2-stp__now-body {
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

/* Controls */
.r-v2-stp__controls {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  padding: var(--r-space-2);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.r-v2-stp__transport,
.r-v2-stp__timeline,
.r-v2-stp__volume {
  display: contents;
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

html[data-bp~="xs"] .r-v2-stp {
  padding: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-stp__now {
  grid-template-columns: 64px minmax(0, 1fr);
  gap: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-stp__cover {
  width: 64px;
  height: 64px;
}

html[data-bp~="xs"] .r-v2-stp__controls {
  flex-wrap: wrap;
}

html[data-bp~="xs"] .r-v2-stp__transport {
  display: flex;
  align-items: center;
  gap: 2px;
}

html[data-bp~="xs"] .r-v2-stp__volume {
  display: flex;
  margin-left: auto;
}

html[data-bp~="xs"] .r-v2-stp__timeline {
  order: 2;
  flex: 1 0 100%;
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  min-width: 0;
}

/* Track list */
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

/* Selected (= "this is the active track") — static primary border +
   soft brand tint. With no thumb, the border is the only signal that
   the row is the player's current focus. */

/* Playing — a brand-coloured arc orbits the row's perimeter so the
   row reads as "in motion" without any pulse or background change.
   A ::before pseudo sits 1px outside the row (`inset: -1px`) so the
   moving gradient only shows as a thin halo around the existing
   border; the row's own surface covers the centre. The pseudo is
   `z-index: -1` (below the row's children) so it never intercepts
   pointer events; `isolation: isolate` pins z-index to this row so
   the negative index can't reach the panel underneath. */
/* Register `--r-stp-orbit-angle` as a typed CSS property so it can be
   smoothly animated between angle values. Without `@property` the angle
   would jump (custom properties default to `<*>`, which is treated as
   a string and can't interpolate). The arc inside the conic gradient
   then advances frame by frame and the pseudo's box stays fixed. */
@property --r-stp-orbit-angle {
  syntax: "<angle>";
  initial-value: 0deg;
  inherits: false;
}

/* Buffering — same orbit, faster cadence so a stall reads as "still
   working" rather than the steady playing tempo. */

/* `--r-stp-orbit-angle` advances non-uniformly across the cycle to
   approximate a perimeter-uniform sweep on a wide rectangle (~10:1
   row aspect). Each keyframe is computed by mapping a uniform
   perimeter step `p` (in pixels) back to the conic-gradient `from`
   angle that puts the arc peak at that perimeter point — i.e.
   `from = atan2(s_x, H/2) − 45°` on the top edge, with analogous
   formulas on the other three edges.
   The previous version had only ~20 keyframes, which left big linear
   segments at the corners: the angular velocity changed by ~10× in
   a single jump (from "crawl on top" to "sprint across side"), and
   the perceived motion stuttered. This version samples the perimeter
   every ~3 % and adds extra in-between samples on either side of each
   corner so the linear interpolation between consecutive frames stays
   close to the true curve. The resulting velocity profile climbs and
   drops smoothly instead of stepping. */

/* Footer */
.r-v2-stp__footer-more {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-2);
  color: var(--r-color-fg-muted);
}

.r-v2-stp__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 16px;
}

.r-v2-stp__footer-total {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  line-height: 16px;
}
</style>
