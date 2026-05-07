<script setup lang="ts">
import axios, { type AxiosRequestConfig } from "axios";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import VolumeControl from "@/components/common/VolumeControl.vue";
import romApi, {
  type SoundtrackAudioMeta,
  type SoundtrackTrackMeta,
} from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import useSoundtrackPlayer, {
  type PlayerMeta,
  type PlayerTrack,
} from "@/stores/soundtrackPlayer";
import type { Events } from "@/types/emitter";
import { formatBytes, FRONTEND_RESOURCES_PATH } from "@/utils";

const props = defineProps<{ rom: DetailedRom }>();
const emit = defineEmits<{
  (e: "upload-tracks"): void;
  (e: "delete-track", fileId: number): void;
}>();
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");

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
  props.rom.files
    .filter(
      (f) => f.category === "soundtrack" && AUDIO_EXTS.has(getExt(f.file_name)),
    )
    .slice()
    .sort((a, b) => a.file_name.localeCompare(b.file_name)),
);

const folderCoverUrl = computed(() => {
  const cover = props.rom.files
    .filter(
      (f) => f.category === "soundtrack" && COVER_EXTS.has(getExt(f.file_name)),
    )
    .sort((a, b) => a.file_name.localeCompare(b.file_name))[0];
  return cover ? fileUrl(cover.id, cover.file_name) : null;
});

const tracksMeta = ref<Map<number, SoundtrackAudioMeta>>(new Map());
const isLoadingMeta = ref(false);
let metaAbort: AbortController | null = null;

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

function coverUrlForMeta(m: SoundtrackAudioMeta | undefined): string | null {
  if (m?.cover_path) return `${FRONTEND_RESOURCES_PATH}/${m.cover_path}`;
  return null;
}

const activeArtUrl = computed(
  () => coverUrlForMeta(activeMeta.value) ?? folderCoverUrl.value,
);

const activeTitle = computed(
  () =>
    activeMeta.value?.title ??
    (activeTrack.value
      ? activeTrack.value.file_name.replace(/\.[^.]+$/, "")
      : ""),
);

const totalDurationSeconds = computed(() => {
  let total = 0;
  for (const t of tracks.value) {
    const d = tracksMeta.value.get(t.id)?.duration_seconds;
    if (d) total += d;
  }
  return total;
});

function trackTitleFor(fileId: number, fallback: string): string {
  return (
    tracksMeta.value.get(fileId)?.title ?? fallback.replace(/\.[^.]+$/, "")
  );
}

function trackArtistFor(fileId: number): string | undefined {
  return tracksMeta.value.get(fileId)?.artist ?? undefined;
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
    emitter?.emit("snackbarShow", {
      msg: t("rom.soundtrack-metadata-error"),
      icon: "mdi-alert",
      color: "red",
      timeout: 3000,
    });
  } finally {
    isLoadingMeta.value = false;
  }
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

onMounted(() => {
  void loadAllMetadata();
});

// Refetch metadata whenever the rom is updated server-side — covers both the
// "new track added" case (IDs grow) and the "same track re-uploaded" case
// (same IDs, new audio_meta) which a track-IDs diff would miss.
watch(
  () => props.rom.updated_at,
  () => void loadAllMetadata(),
);

onBeforeUnmount(() => {
  metaAbort?.abort();
});

function selectTrack(fileId: number) {
  const track = tracks.value.find((t) => t.id === fileId);
  if (!track) return;

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
  const target = playerTracks.find((p) => p.fileId === fileId)!;
  player.play(target, metas[fileId]);
}

function onDelete(fileId: number) {
  if (activeTrackId.value === fileId) {
    player.stop();
  }
  emit("delete-track", fileId);
}

function chips(meta: SoundtrackAudioMeta | undefined) {
  if (!meta) return [];
  const items: { icon: string; label: string }[] = [];
  if (meta.album) items.push({ icon: "mdi-album", label: meta.album });
  if (meta.artist)
    items.push({ icon: "mdi-account-music", label: meta.artist });
  if (meta.year) items.push({ icon: "mdi-calendar", label: meta.year });
  if (meta.genre)
    items.push({ icon: "mdi-music-clef-treble", label: meta.genre });
  if (meta.track) items.push({ icon: "mdi-numeric", label: `#${meta.track}` });
  if (meta.disc)
    items.push({ icon: "mdi-disc", label: `${t("rom.disc")} ${meta.disc}` });
  return items;
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
  return `${fmt(v)} of ${fmt(duration.value)}`;
}
</script>

<template>
  <div class="pa-2">
    <div v-if="activeTrack" class="d-flex align-center mb-4 ga-4 flex-wrap">
      <div
        class="disc-wrapper rounded-circle overflow-hidden position-relative flex-shrink-0"
        :class="{ spinning: isPlaying }"
      >
        <img
          v-if="activeArtUrl"
          :src="activeArtUrl"
          class="disc w-100 h-100 d-block rounded-circle"
          alt=""
        />
        <div
          v-else
          class="disc w-100 h-100 rounded-circle d-flex align-center justify-center bg-toplayer text-medium-emphasis"
        >
          <v-icon size="64">mdi-music-note</v-icon>
        </div>
        <div
          v-if="isBuffering"
          class="buffering-overlay position-absolute d-flex align-center justify-center rounded-circle"
        >
          <v-progress-circular
            indeterminate
            size="40"
            width="3"
            color="white"
          />
        </div>
      </div>
      <div class="flex-grow-1" style="min-width: 200px">
        <div class="text-h6 text-truncate">{{ activeTitle }}</div>
        <div
          v-if="activeMeta?.artist"
          class="text-subtitle-2 text-medium-emphasis"
        >
          {{ activeMeta.artist }}
        </div>
        <div class="d-flex flex-wrap ga-2 mt-2">
          <v-chip
            v-for="(c, i) in chips(activeMeta)"
            :key="i"
            size="small"
            variant="tonal"
            :prepend-icon="c.icon"
          >
            {{ c.label }}
          </v-chip>
        </div>
      </div>
    </div>
    <div
      v-if="activeTrack"
      class="d-flex align-center mb-3 ga-2 px-2"
      role="region"
      :aria-label="t('rom.soundtrack-player')"
    >
      <v-btn
        icon="mdi-skip-previous"
        variant="text"
        size="default"
        :disabled="!hasPrevious"
        :aria-label="t('rom.soundtrack-previous')"
        @click="player.previous()"
      />
      <v-btn
        :icon="isPlaying ? 'mdi-pause-circle' : 'mdi-play-circle'"
        variant="text"
        size="large"
        :aria-label="
          isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
        "
        @click="player.togglePlayPause()"
      />
      <v-btn
        icon="mdi-skip-next"
        variant="text"
        size="default"
        :disabled="!hasNext"
        :aria-label="t('rom.soundtrack-next')"
        @click="player.next()"
      />
      <span class="text-caption text-medium-emphasis" style="width: 40px">
        {{ fmt(currentTime) }}
      </span>
      <v-slider
        :model-value="currentTime"
        :max="duration || 0"
        :step="0.1"
        density="compact"
        hide-details
        color="primary"
        thumb-size="14"
        track-size="3"
        class="flex-grow-1"
        :aria-label="t('rom.soundtrack-seek')"
        :aria-valuetext="seekValueText(currentTime)"
        @update:model-value="(v: number) => player.seek(v)"
      />
      <span
        class="text-caption text-medium-emphasis text-right"
        style="width: 40px"
      >
        {{ fmt(duration) }}
      </span>
      <VolumeControl btn-size="default" />
    </div>
    <v-list density="compact" class="bg-toplayer rounded">
      <v-list-item
        v-for="track in tracks"
        :key="track.id"
        :active="activeTrackId === track.id"
        @click="selectTrack(track.id)"
      >
        <template #prepend>
          <div
            class="track-thumb mr-3 rounded overflow-hidden d-flex align-center justify-center flex-shrink-0 position-relative"
          >
            <img
              v-if="thumbForTrack(track.id)"
              :src="thumbForTrack(track.id) ?? ''"
              class="w-100 h-100"
              loading="lazy"
              alt=""
            />
            <v-icon v-else>
              {{
                activeTrackId === track.id
                  ? "mdi-volume-high"
                  : "mdi-music-note"
              }}
            </v-icon>
            <div
              v-if="activeTrackId === track.id && isBuffering"
              class="buffering-overlay position-absolute d-flex align-center justify-center rounded"
            >
              <v-progress-circular
                indeterminate
                size="18"
                width="2"
                color="white"
              />
            </div>
          </div>
        </template>
        <v-list-item-title>
          {{ trackTitleFor(track.id, track.file_name) }}
        </v-list-item-title>
        <v-list-item-subtitle v-if="trackArtistFor(track.id)">
          {{ trackArtistFor(track.id) }}
        </v-list-item-subtitle>
        <template #append>
          <span
            v-if="trackDurationFor(track.id)"
            class="text-caption text-medium-emphasis mr-3"
          >
            {{ fmt(trackDurationFor(track.id)) }}
          </span>
          <span class="text-caption text-medium-emphasis mr-2">
            {{ formatBytes(track.file_size_bytes) }}
          </span>
          <v-btn
            icon="mdi-delete"
            variant="text"
            size="small"
            class="text-romm-red"
            :aria-label="t('rom.soundtrack-delete-track')"
            @click.stop="onDelete(track.id)"
          />
        </template>
      </v-list-item>
    </v-list>
    <div class="d-flex align-center justify-space-between mt-3">
      <span
        v-if="totalDurationSeconds > 0"
        class="text-caption text-medium-emphasis"
      >
        {{ tracks.length }} · {{ fmt(totalDurationSeconds) }}
      </span>
      <span v-else />
      <v-btn
        prepend-icon="mdi-cloud-upload-outline"
        variant="tonal"
        size="small"
        @click="emit('upload-tracks')"
      >
        {{ t("rom.upload-tracks") }}
      </v-btn>
    </div>
  </div>
</template>

<style scoped>
.disc-wrapper {
  width: 180px;
  height: 180px;
  box-shadow:
    0 0 0 6px rgba(0, 0, 0, 0.55),
    0 8px 24px rgba(0, 0, 0, 0.45);
  background: radial-gradient(
    circle at center,
    transparent 0,
    transparent 22px,
    rgba(0, 0, 0, 0.65) 22px,
    rgba(0, 0, 0, 0.65) 30px,
    transparent 31px
  );
}

.disc-wrapper::after {
  content: "";
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(var(--v-theme-surface), 1);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  box-shadow: inset 0 0 0 2px rgba(0, 0, 0, 0.6);
}

.disc {
  object-fit: cover;
  animation: spin 12s linear infinite;
  animation-play-state: paused;
}

.disc-wrapper.spinning .disc {
  animation-play-state: running;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .disc,
  .disc-wrapper.spinning .disc {
    animation: none;
  }
}

.track-thumb {
  width: 40px;
  height: 40px;
  background: rgba(0, 0, 0, 0.25);
}

.track-thumb img {
  object-fit: cover;
}

.buffering-overlay {
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 3;
}
</style>
