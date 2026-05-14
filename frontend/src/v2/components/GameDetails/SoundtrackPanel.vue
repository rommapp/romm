<script setup lang="ts">
// SoundtrackPanel — v2 embedded soundtrack player.
//
// Consumes the shared `useSoundtrackPlayer` store (the actual HTMLAudioElement
// lives inside SoundtrackMiniPlayer, which stays mounted app-wide). Clicking
// a track here fills the store playlist and calls `player.play(...)`; the
// mini-player hides automatically when route.query.subtab === "soundtrack",
// so only one "now playing" surface is ever on screen.
//
// Key difference from the v1 player: metadata chips are shown per track AND
// in the now-playing header, not just in the header.
import { RBtn, RChip, RIcon, RSlider, RSpinner } from "@v2/lib";
import axios, { type AxiosRequestConfig } from "axios";
import { storeToRefs } from "pinia";
import {
  computed,
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import romApi, {
  type SoundtrackAudioMeta,
  type SoundtrackTrackMeta,
} from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import useSoundtrackPlayer, {
  type PlayerMeta,
  type PlayerTrack,
} from "@/stores/soundtrackPlayer";
import { FRONTEND_RESOURCES_PATH, formatBytes } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";

// The volume/mute control widget is v1 code; it writes straight to the
// shared store so it Just Works inside our panel too. Lazy-load it so the
// panel can ship without bringing v-slider-eager into the initial chunk.
const VolumeControl = defineAsyncComponent(
  () => import("@/components/common/VolumeControl.vue"),
);

const props = defineProps<{ rom: DetailedRom }>();
const emit = defineEmits<{
  (e: "upload-tracks"): void;
  (e: "delete-track", fileId: number): void;
}>();

const snackbar = useSnackbar();

const player = useSoundtrackPlayer();
const {
  track: activeStoreTrack,
  isPlaying,
  isBuffering,
  currentTime,
  duration,
  hasPrevious,
  hasNext,
} = storeToRefs(player);

// ---------- Track + cover discovery ----------
const AUDIO_EXTS = new Set([
  "mp3",
  "ogg",
  "oga",
  "opus",
  "m4a",
  "aac",
  "wav",
  "flac",
]);
const COVER_EXTS = new Set(["png", "jpg", "jpeg", "webp", "gif"]);

function getExt(name: string): string {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function fileUrl(fileId: number, fileName: string): string {
  return `/api/roms/${fileId}/files/content/${encodeURIComponent(fileName)}`;
}

const tracks = computed(() =>
  (props.rom.files ?? [])
    .filter(
      (f) => f.category === "soundtrack" && AUDIO_EXTS.has(getExt(f.file_name)),
    )
    .slice()
    .sort((a, b) => a.file_name.localeCompare(b.file_name)),
);

const folderCoverUrl = computed(() => {
  const cover = (props.rom.files ?? [])
    .filter(
      (f) => f.category === "soundtrack" && COVER_EXTS.has(getExt(f.file_name)),
    )
    .sort((a, b) => a.file_name.localeCompare(b.file_name))[0];
  return cover ? fileUrl(cover.id, cover.file_name) : null;
});

// ---------- Metadata fetch ----------
const tracksMeta = ref<Map<number, SoundtrackAudioMeta>>(new Map());
const isLoadingMeta = ref(false);
let metaAbort: AbortController | null = null;

function coverUrlForMeta(m: SoundtrackAudioMeta | undefined): string | null {
  if (m?.cover_path) return `${FRONTEND_RESOURCES_PATH}/${m.cover_path}`;
  return null;
}

function toPlayerMeta(m: SoundtrackAudioMeta | undefined): PlayerMeta {
  return {
    title: m?.title ?? undefined,
    artist: m?.artist ?? undefined,
    album: m?.album ?? undefined,
    year: m?.year ?? undefined,
    genre: m?.genre ?? undefined,
    track: m?.track ?? undefined,
    disc: m?.disc ?? undefined,
    duration: m?.duration_seconds ?? undefined,
    coverUrl: coverUrlForMeta(m) ?? undefined,
    folderCoverUrl: folderCoverUrl.value ?? undefined,
  };
}

function syncStorePlaylist() {
  if (player.activePlaylistRomId !== props.rom.id) return;
  const playerTracks: PlayerTrack[] = tracks.value.map((t) => ({
    romId: props.rom.id,
    fileId: t.id,
    fileName: t.file_name,
    url: fileUrl(t.id, t.file_name),
  }));
  const metas: Record<number, PlayerMeta> = {};
  for (const t of tracks.value) {
    metas[t.id] = toPlayerMeta(tracksMeta.value.get(t.id));
  }
  player.loadPlaylistForRom(props.rom.id, playerTracks, metas);
}

async function loadAllMetadata() {
  metaAbort?.abort();
  metaAbort = new AbortController();
  isLoadingMeta.value = true;
  try {
    const { data } = await romApi.getSoundtrackMetadata({
      romId: props.rom.id,
      signal: metaAbort.signal,
    });
    const next = new Map<number, SoundtrackAudioMeta>();
    for (const row of data as SoundtrackTrackMeta[]) {
      if (row.audio_meta) next.set(row.file_id, row.audio_meta);
    }
    tracksMeta.value = next;
    syncStorePlaylist();
  } catch (err: unknown) {
    const maybeCfg = err as { config?: AxiosRequestConfig };
    if (axios.isCancel(err) || maybeCfg.config?.signal?.aborted) return;
    snackbar.error("Couldn't load soundtrack metadata.", {
      icon: "mdi-alert",
      timeout: 3000,
    });
  } finally {
    isLoadingMeta.value = false;
  }
}

onMounted(() => {
  void loadAllMetadata();
});

// Refetch when the rom updates (new tracks, re-tagged files, etc.).
watch(
  () => props.rom.updated_at,
  () => void loadAllMetadata(),
);

onBeforeUnmount(() => {
  metaAbort?.abort();
});

// ---------- Active-track + derived metadata ----------
const activeTrackId = computed(() =>
  activeStoreTrack.value && activeStoreTrack.value.romId === props.rom.id
    ? activeStoreTrack.value.fileId
    : null,
);

const activeTrack = computed(() =>
  tracks.value.find((t) => t.id === activeTrackId.value),
);

const activeMeta = computed<SoundtrackAudioMeta | undefined>(() =>
  activeTrackId.value != null
    ? tracksMeta.value.get(activeTrackId.value)
    : undefined,
);

const activeArtUrl = computed(
  () =>
    coverUrlForMeta(activeMeta.value) ??
    folderCoverUrl.value ??
    "/assets/default/album_cover.jpg",
);

const activeTitle = computed(
  () =>
    activeMeta.value?.title ??
    (activeTrack.value
      ? activeTrack.value.file_name.replace(/\.[^.]+$/, "")
      : ""),
);

// ---------- Per-track helpers ----------
function trackTitleFor(fileId: number, fallback: string): string {
  return (
    tracksMeta.value.get(fileId)?.title ?? fallback.replace(/\.[^.]+$/, "")
  );
}

function trackSubtitleFor(fileId: number): string {
  const m = tracksMeta.value.get(fileId);
  if (!m) return "";
  const parts: string[] = [];
  if (m.artist) parts.push(m.artist);
  if (m.album) parts.push(m.album);
  return parts.join(" · ");
}

function trackDurationFor(fileId: number): number | undefined {
  return tracksMeta.value.get(fileId)?.duration_seconds ?? undefined;
}

function thumbForTrack(fileId: number): string | null {
  return (
    coverUrlForMeta(tracksMeta.value.get(fileId)) ??
    folderCoverUrl.value ??
    null
  );
}

// Chips shown in the now-playing header.
type ChipItem = { icon: string; label: string; color?: string };

function headerChips(meta: SoundtrackAudioMeta | undefined): ChipItem[] {
  if (!meta) return [];
  const items: ChipItem[] = [];
  if (meta.album) items.push({ icon: "mdi-album", label: meta.album });
  if (meta.artist)
    items.push({ icon: "mdi-account-music", label: meta.artist });
  if (meta.year)
    items.push({ icon: "mdi-calendar", label: meta.year, color: "accent" });
  if (meta.genre)
    items.push({ icon: "mdi-music-clef-treble", label: meta.genre });
  if (meta.track)
    items.push({ icon: "mdi-numeric", label: `Track ${meta.track}` });
  if (meta.disc) items.push({ icon: "mdi-disc", label: `Disc ${meta.disc}` });
  return items;
}

// Compact chips shown on each track row — keep it tight so rows don't bloat.
function rowChips(fileId: number): ChipItem[] {
  const meta = tracksMeta.value.get(fileId);
  if (!meta) return [];
  const items: ChipItem[] = [];
  if (meta.year)
    items.push({ icon: "mdi-calendar", label: meta.year, color: "accent" });
  if (meta.genre)
    items.push({ icon: "mdi-music-clef-treble", label: meta.genre });
  if (meta.track) items.push({ icon: "mdi-numeric", label: `#${meta.track}` });
  if (meta.disc) items.push({ icon: "mdi-disc", label: meta.disc });
  return items;
}

// ---------- Totals ----------
const totalDurationSeconds = computed(() => {
  let total = 0;
  for (const t of tracks.value) {
    const d = tracksMeta.value.get(t.id)?.duration_seconds;
    if (d) total += d;
  }
  return total;
});

// ---------- Playback ----------
function selectTrack(fileId: number) {
  const target = tracks.value.find((t) => t.id === fileId);
  if (!target) return;

  const playerTracks: PlayerTrack[] = tracks.value.map((t) => ({
    romId: props.rom.id,
    fileId: t.id,
    fileName: t.file_name,
    url: fileUrl(t.id, t.file_name),
  }));
  const metas: Record<number, PlayerMeta> = {};
  for (const t of tracks.value) {
    metas[t.id] = toPlayerMeta(tracksMeta.value.get(t.id));
  }
  player.loadPlaylistForRom(props.rom.id, playerTracks, metas);
  const entry = playerTracks.find((p) => p.fileId === fileId)!;
  player.play(entry, metas[fileId]);
}

function onDelete(fileId: number) {
  if (activeTrackId.value === fileId) player.stop();
  emit("delete-track", fileId);
}

// ---------- Formatters ----------
function fmt(s: number | undefined | null) {
  if (s == null || !Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${sec}`;
}

function seekValueText(v: number): string {
  return `${fmt(v)} of ${fmt(duration.value)}`;
}
</script>

<template>
  <div class="r-v2-stp">
    <!-- Now playing / placeholder header -->
    <header class="r-v2-stp__now">
      <div
        class="r-v2-stp__cover"
        :class="{ 'r-v2-stp__cover--spinning': activeTrack && isPlaying }"
      >
        <img
          v-if="activeArtUrl"
          :src="activeArtUrl"
          class="r-v2-stp__cover-img"
          alt=""
        />
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
          <span v-if="isLoadingMeta">
            <RSpinner :size="14" />
            Loading metadata…
          </span>
          <span v-else-if="activeTrack">
            {{ isPlaying ? "Now playing" : "Paused" }}
          </span>
          <span v-else>
            {{ tracks.length }} track{{ tracks.length === 1 ? "" : "s" }}
          </span>
        </div>
        <h3 class="r-v2-stp__now-title">
          {{ activeTrack ? activeTitle : "Pick a track to start playing" }}
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
          Album art, artist and track metadata will appear here once you start
          playing.
        </div>
      </div>
    </header>

    <!-- Controls (only meaningful with an active track) -->
    <div
      v-if="activeTrack"
      class="r-v2-stp__controls"
      role="region"
      aria-label="Soundtrack player"
    >
      <RBtn
        variant="text"
        size="small"
        :disabled="!hasPrevious"
        prepend-icon="mdi-skip-previous"
        @click="player.previous()"
      />
      <RBtn
        variant="text"
        size="large"
        :prepend-icon="isPlaying ? 'mdi-pause-circle' : 'mdi-play-circle'"
        @click="player.togglePlayPause()"
      />
      <RBtn
        variant="text"
        size="small"
        :disabled="!hasNext"
        prepend-icon="mdi-skip-next"
        @click="player.next()"
      />
      <span class="r-v2-stp__time">{{ fmt(currentTime) }}</span>
      <RSlider
        :model-value="currentTime"
        :max="duration || 0"
        :step="0.1"
        color="primary"
        class="r-v2-stp__slider"
        aria-label="Seek"
        :aria-valuetext="seekValueText(currentTime)"
        @update:model-value="(v: number) => player.seek(v)"
      />
      <span class="r-v2-stp__time r-v2-stp__time--right">
        {{ fmt(duration) }}
      </span>
      <VolumeControl btn-size="small" />
    </div>

    <!-- Track list -->
    <ul class="r-v2-stp__list">
      <li
        v-for="track in tracks"
        :key="track.id"
        class="r-v2-stp__row"
        :class="{ 'r-v2-stp__row--active': activeTrackId === track.id }"
      >
        <button
          type="button"
          class="r-v2-stp__row-btn"
          :aria-label="`Play ${trackTitleFor(track.id, track.file_name)}`"
          @click="selectTrack(track.id)"
        >
          <div class="r-v2-stp__row-thumb">
            <img
              v-if="thumbForTrack(track.id)"
              :src="thumbForTrack(track.id) ?? ''"
              alt=""
              loading="lazy"
            />
            <RIcon
              v-else
              :icon="
                activeTrackId === track.id
                  ? 'mdi-volume-high'
                  : 'mdi-music-note'
              "
            />
            <div
              v-if="activeTrackId === track.id && isBuffering"
              class="r-v2-stp__row-buffering"
              aria-hidden="true"
            >
              <RSpinner :size="16" :width="2" color="white" />
            </div>
            <div
              v-else-if="activeTrackId === track.id && isPlaying"
              class="r-v2-stp__row-playing"
              aria-hidden="true"
            >
              <RIcon icon="mdi-pause" size="18" color="white" />
            </div>
          </div>
          <div class="r-v2-stp__row-meta">
            <div class="r-v2-stp__row-title">
              {{ trackTitleFor(track.id, track.file_name) }}
            </div>
            <div
              v-if="trackSubtitleFor(track.id)"
              class="r-v2-stp__row-subtitle"
            >
              {{ trackSubtitleFor(track.id) }}
            </div>
            <div v-if="rowChips(track.id).length" class="r-v2-stp__row-chips">
              <RChip
                v-for="(c, i) in rowChips(track.id)"
                :key="`r-${track.id}-${i}`"
                size="x-small"
                variant="translucent"
                :color="c.color"
                :prepend-icon="c.icon"
              >
                {{ c.label }}
              </RChip>
            </div>
          </div>
        </button>

        <div class="r-v2-stp__row-right">
          <span
            v-if="trackDurationFor(track.id)"
            class="r-v2-stp__row-duration"
          >
            {{ fmt(trackDurationFor(track.id)) }}
          </span>
          <span class="r-v2-stp__row-size">
            {{ formatBytes(track.file_size_bytes) }}
          </span>
          <RBtn
            variant="text"
            size="x-small"
            color="romm-red"
            prepend-icon="mdi-delete"
            aria-label="Delete track"
            @click.stop="onDelete(track.id)"
          />
        </div>
      </li>
    </ul>

    <!-- Footer -->
    <footer class="r-v2-stp__footer">
      <span v-if="totalDurationSeconds > 0" class="r-v2-stp__footer-total">
        {{ tracks.length }} track{{ tracks.length === 1 ? "" : "s" }} ·
        {{ fmt(totalDurationSeconds) }}
      </span>
    </footer>
  </div>
</template>

<style scoped>
.r-v2-stp {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
  padding: var(--r-space-5);
}

/* Now playing / placeholder header */
.r-v2-stp__now {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: var(--r-space-5);
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

.r-v2-stp__cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  animation: r-v2-stp-spin 12s linear infinite;
  animation-play-state: paused;
}

.r-v2-stp__cover--spinning .r-v2-stp__cover-img {
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
}

@keyframes r-v2-stp-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-v2-stp__cover-img {
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
  -webkit-box-orient: vertical;
}

.r-v2-stp__now-artist {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-md);
}

.r-v2-stp__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-1);
  margin-top: var(--r-space-1);
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

/* Track list */
.r-v2-stp__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

.r-v2-stp__row {
  display: flex;
  align-items: stretch;
  gap: var(--r-space-2);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface);
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-stp__row:hover {
  border-color: var(--r-color-brand-primary-hover);
}

.r-v2-stp__row--active {
  border-color: var(--r-color-brand-primary);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent),
    var(--r-color-surface)
  );
}

.r-v2-stp__row-btn {
  appearance: none;
  border: 0;
  background: transparent;
  padding: var(--r-space-2) var(--r-space-3);
  flex: 1;
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: var(--r-space-3);
  align-items: center;
  cursor: pointer;
  color: var(--r-color-fg);
  min-width: 0;
  text-align: left;
}

.r-v2-stp__row-thumb {
  width: 48px;
  height: 48px;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  position: relative;
  background: var(--r-color-bg);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-muted);
  display: grid;
  place-items: center;
}

.r-v2-stp__row-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.r-v2-stp__row-buffering,
.r-v2-stp__row-playing {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 50%, transparent);
}

.r-v2-stp__row-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-stp__row-title {
  font-weight: var(--r-font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-stp__row-subtitle {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-stp__row-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.r-v2-stp__row-right {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  padding: 0 var(--r-space-2);
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}

.r-v2-stp__row-duration {
  min-width: 44px;
  text-align: right;
}

/* Footer */
.r-v2-stp__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--r-space-2);
  border-top: 1px dashed var(--r-color-border);
}

.r-v2-stp__footer-total {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}
</style>
