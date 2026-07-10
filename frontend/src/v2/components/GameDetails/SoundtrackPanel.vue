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
import { useI18n } from "vue-i18n";
import type {
  TrackMetaSchema,
  SoundtrackTrackMetaSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import useSoundtrackPlayer, {
  type PlayerMeta,
  type PlayerTrack,
} from "@/stores/soundtrackPlayer";
import { FRONTEND_RESOURCES_PATH, formatBytes } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";

// Volume / mute widget — v2 native (RMenu + RSlider + RBtn). The
// shared `useSoundtrackPlayer` store owns the volume / muted state so
// the same widget can sit in the mini-player too without needing a
// local model.
const VolumeControl = defineAsyncComponent(
  () => import("@/v2/components/Soundtrack/VolumeControl.vue"),
);

const props = defineProps<{ rom: DetailedRom }>();
const emit = defineEmits<{
  (e: "upload-tracks"): void;
  (e: "delete-track", fileId: number): void;
}>();

const { t } = useI18n();
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
const tracksMeta = ref<Map<number, TrackMetaSchema>>(new Map());
const isLoadingMeta = ref(false);
let metaAbort: AbortController | null = null;

function coverUrlForMeta(m: TrackMetaSchema | undefined): string | null {
  if (m?.cover_path) return `${FRONTEND_RESOURCES_PATH}/${m.cover_path}`;
  return null;
}

function toPlayerMeta(m: TrackMetaSchema | undefined): PlayerMeta {
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
    const next = new Map<number, TrackMetaSchema>();
    for (const row of data as SoundtrackTrackMetaSchema[]) {
      if (row.track_meta) next.set(row.file_id, row.track_meta);
    }
    tracksMeta.value = next;
    syncStorePlaylist();
  } catch (err: unknown) {
    const maybeCfg = err as { config?: AxiosRequestConfig };
    if (axios.isCancel(err) || maybeCfg.config?.signal?.aborted) return;
    snackbar.error(t("rom.cant-load-soundtrack-meta"), {
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

const activeMeta = computed<TrackMetaSchema | undefined>(() =>
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

// Compact chips shown on each track row — keep it tight so rows don't bloat.
function rowChips(fileId: number): ChipItem[] {
  const meta = tracksMeta.value.get(fileId);
  if (!meta) return [];
  const items: ChipItem[] = [];
  if (meta.year)
    items.push({
      icon: "mdi-calendar",
      label: String(meta.year),
      color: "accent",
    });
  if (meta.genre)
    items.push({ icon: "mdi-music-clef-treble", label: meta.genre });
  if (meta.track) items.push({ icon: "mdi-numeric", label: `#${meta.track}` });
  if (meta.disc) items.push({ icon: "mdi-disc", label: String(meta.disc) });
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

// Mirror the saves/states pattern: synthesize an anchor click against
// the file content endpoint so the browser routes the download with
// the original filename instead of opening it in a new tab.
function downloadTrack(track: { id: number; file_name: string }) {
  const a = document.createElement("a");
  a.href = fileUrl(track.id, track.file_name);
  a.download = track.file_name;
  document.body.appendChild(a);
  a.click();
  a.remove();
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
  return t("rom.seek-progress", {
    current: fmt(v),
    duration: fmt(duration.value),
  });
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
            {{ t("rom.loading-metadata") }}
          </span>
          <span v-else-if="activeTrack">
            {{ isPlaying ? t("rom.now-playing") : t("rom.paused") }}
          </span>
          <span v-else>
            {{
              t("rom.tracks-n", tracks.length, { named: { n: tracks.length } })
            }}
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
      <VolumeControl size="small" />
    </div>

    <!-- Track list -->
    <ul class="r-v2-stp__list">
      <li
        v-for="(track, trackIdx) in tracks"
        :key="track.id"
        class="r-v2-stp__row r-v2-asset-fade"
        :class="{
          'r-v2-stp__row--active': activeTrackId === track.id,
          'r-v2-stp__row--playing':
            activeTrackId === track.id && isPlaying && !isBuffering,
          'r-v2-stp__row--buffering': activeTrackId === track.id && isBuffering,
        }"
        :style="{ '--asset-fade-i': trackIdx }"
      >
        <button
          type="button"
          class="r-v2-stp__row-btn"
          :aria-label="
            t('rom.play-track', {
              title: trackTitleFor(track.id, track.file_name),
            })
          "
          @click="selectTrack(track.id)"
        >
          <!-- No per-track thumb: playback state is conveyed entirely
               by the row's border + a subtle pulsing glow when the
               track is actually playing (vs. just selected/paused). -->
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
            icon="mdi-download-outline"
            variant="text"
            size="small"
            :tooltip="t('common.download')"
            :aria-label="
              t('rom.download-named', {
                name: trackTitleFor(track.id, track.file_name),
              })
            "
            @click.stop="downloadTrack(track)"
          />
          <RBtn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="romm-red"
            :tooltip="t('common.delete')"
            :aria-label="t('rom.soundtrack-delete-track')"
            @click.stop="onDelete(track.id)"
          />
        </div>
      </li>
    </ul>

    <!-- Footer -->
    <footer class="r-v2-stp__footer">
      <span v-if="totalDurationSeconds > 0" class="r-v2-stp__footer-total">
        {{
          t("rom.tracks-summary", {
            count: tracks.length,
            duration: fmt(totalDurationSeconds),
          })
        }}
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
  /* Soundtrack tab lives inside MediaTab's `__panel` (a flex item with
     `flex: 1; min-height: 0`), but neither MediaTab nor the GameDetails
     panel scroll for this child — the GameDetails panel is locked to
     viewport height via `.r-v2-media { height: 100% }`. Without an
     internal scroll context the last track + footer get clipped by the
     panel's overflow boundary. Owning the scroll here (full panel
     scrolls together — now-playing header, controls and list) keeps
     the whole thing reachable without restructuring MediaTab's chain. */
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-v2-stp::-webkit-scrollbar {
  width: 4px;
}
.r-v2-stp::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 2px;
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
  line-clamp: 2;
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

/* Selected (= "this is the active track") — static primary border +
   soft brand tint. With no thumb, the border is the only signal that
   the row is the player's current focus. */
.r-v2-stp__row--active {
  border-color: var(--r-color-brand-primary);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent),
    var(--r-color-surface)
  );
}

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

.r-v2-stp__row--playing,
.r-v2-stp__row--buffering {
  /* Anchor for the orbit pseudo. */
  position: relative;
}
.r-v2-stp__row--playing::before,
.r-v2-stp__row--buffering::before {
  content: "";
  position: absolute;
  /* The pseudo covers the row plus a 1px overshoot on every side so
     the visible ring lands right on the row's border. Padding sets
     the ring thickness; the mask-composite trick below clips the
     conic gradient down to that ring. Thicker ring (3px) gives the
     arcs more weight on the perimeter. */
  inset: -1px;
  padding: 3px;
  border-radius: inherit;
  /* Two bright arcs sitting 180° apart so the row reads as having
     two pulses chasing each other. Each arc spans ~40% of the
     circumference with a long, smooth tail-in / tail-out at six
     intermediate opacities — that breaks up the visible staircase
     conic gradients normally show at a small number of stops. The
     conic gradient's `from` angle is the animated custom property
     so only the arc pattern travels; the pseudo's box stays put. */
  background: conic-gradient(
    from var(--r-stp-orbit-angle),
    /* Arc A — peak at 12.5%, ~40% wide with a long diffuse tail. */
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 0%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 4%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 8%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 11%,
    var(--r-color-brand-primary) 12.5%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 14%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 17%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 21%,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 25%,
    transparent 32%,
    /* Empty quadrant — clear separation between the two pulses. */ transparent
      50%,
    /* Arc B — same envelope, 180° away from arc A. */
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 50%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 54%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 58%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 61%,
    var(--r-color-brand-primary) 62.5%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 64%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 67%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 71%,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 75%,
    transparent 82%,
    transparent 100%
  );
  /* "Gradient border" mask: paint the conic gradient only on the
     padding ring. The two solid masks (one clipped to `content-box`,
     the other to the full box) are XORed — what's left is the ring
     between them. */
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  mask-composite: exclude;
  /* Sub-pixel blur softens any residual conic-gradient banding that
     the gradient stops alone can't fully erase. */
  filter: blur(0.4px);
  pointer-events: none;
  animation: r-v2-stp-row-spin 3.2s linear infinite;
}

/* Buffering — same orbit, faster cadence so a stall reads as "still
   working" rather than the steady playing tempo. */
.r-v2-stp__row--buffering::before {
  animation-duration: 1.2s;
}

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
@keyframes r-v2-stp-row-spin {
  /* Top edge — right half, from start point (45°) to the right corner.
     Velocity gradually drops as we approach the corner. */
  0% {
    --r-stp-orbit-angle: 0deg;
  }
  2.5% {
    --r-stp-orbit-angle: 22.7deg;
  }
  5% {
    --r-stp-orbit-angle: 30.5deg;
  }
  7.5% {
    --r-stp-orbit-angle: 34.3deg;
  }
  10% {
    --r-stp-orbit-angle: 36.6deg;
  }
  12.5% {
    --r-stp-orbit-angle: 38deg;
  }
  15% {
    --r-stp-orbit-angle: 39.1deg;
  }
  17.5% {
    --r-stp-orbit-angle: 39.8deg;
  }
  20% {
    --r-stp-orbit-angle: 40.4deg;
  }
  /* Right corner area — velocity gradually picks up. Extra samples
     here so the transition into the side doesn't read as a jump. */
  22.5% {
    --r-stp-orbit-angle: 41.5deg;
  }
  23.5% {
    --r-stp-orbit-angle: 43.5deg;
  }
  24.25% {
    --r-stp-orbit-angle: 46deg;
  }
  25% {
    --r-stp-orbit-angle: 49.3deg;
  }
  /* Bottom edge — slow at first, then sprinting through the centre. */
  27.5% {
    --r-stp-orbit-angle: 49.8deg;
  }
  30% {
    --r-stp-orbit-angle: 50.5deg;
  }
  32.5% {
    --r-stp-orbit-angle: 51.3deg;
  }
  35% {
    --r-stp-orbit-angle: 52.5deg;
  }
  37.5% {
    --r-stp-orbit-angle: 54.2deg;
  }
  40% {
    --r-stp-orbit-angle: 56.9deg;
  }
  42.5% {
    --r-stp-orbit-angle: 61.8deg;
  }
  45% {
    --r-stp-orbit-angle: 73.2deg;
  }
  47% {
    --r-stp-orbit-angle: 100deg;
  }
  48.3% {
    --r-stp-orbit-angle: 135deg;
  }
  49.5% {
    --r-stp-orbit-angle: 170deg;
  }
  51.7% {
    --r-stp-orbit-angle: 198.4deg;
  }
  55% {
    --r-stp-orbit-angle: 210.5deg;
  }
  57.5% {
    --r-stp-orbit-angle: 214.3deg;
  }
  60% {
    --r-stp-orbit-angle: 216.6deg;
  }
  62.5% {
    --r-stp-orbit-angle: 218.1deg;
  }
  65% {
    --r-stp-orbit-angle: 219.1deg;
  }
  67.5% {
    --r-stp-orbit-angle: 219.8deg;
  }
  70% {
    --r-stp-orbit-angle: 220.4deg;
  }
  /* Left corner area — symmetric with the right corner. */
  72.5% {
    --r-stp-orbit-angle: 221.5deg;
  }
  73.5% {
    --r-stp-orbit-angle: 223.5deg;
  }
  74.25% {
    --r-stp-orbit-angle: 226deg;
  }
  75% {
    --r-stp-orbit-angle: 229.3deg;
  }
  /* Top edge, left half coming back to the start position. */
  77.5% {
    --r-stp-orbit-angle: 229.8deg;
  }
  80% {
    --r-stp-orbit-angle: 230.5deg;
  }
  82.5% {
    --r-stp-orbit-angle: 231.3deg;
  }
  85% {
    --r-stp-orbit-angle: 232.5deg;
  }
  87.5% {
    --r-stp-orbit-angle: 234.2deg;
  }
  90% {
    --r-stp-orbit-angle: 236.9deg;
  }
  92.5% {
    --r-stp-orbit-angle: 241.8deg;
  }
  95% {
    --r-stp-orbit-angle: 253.2deg;
  }
  97% {
    --r-stp-orbit-angle: 280deg;
  }
  98.3% {
    --r-stp-orbit-angle: 315deg;
  }
  99.5% {
    --r-stp-orbit-angle: 350deg;
  }
  100% {
    --r-stp-orbit-angle: 360deg;
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-v2-stp__row--playing::before,
  .r-v2-stp__row--buffering::before {
    animation: none;
    /* Drop the moving arc for a soft static halo so playing is still
       distinguishable from paused without motion. */
    background: none;
    box-shadow: 0 0 0 3px
      color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
  }
}

.r-v2-stp__row-btn {
  appearance: none;
  border: 0;
  background: transparent;
  padding: var(--r-space-2) var(--r-space-3);
  flex: 1;
  display: flex;
  align-items: center;
  cursor: pointer;
  color: var(--r-color-fg);
  min-width: 0;
  text-align: left;
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
