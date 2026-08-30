<script setup lang="ts">
// LiveSessionCard — a multiplayer streaming session another user is hosting
// right now, shown on the Home row. Clicking asks to join and then opens
// the stream as a viewer.
import { RChip, RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { JoinableSession } from "@/stores/streaming";
import GameCover from "@/v2/components/shared/GameCover.vue";
import type { CoverArtRom } from "@/v2/composables/useCoverArt";
import { useJoinStreamConfirm } from "@/v2/composables/useJoinStreamConfirm";

interface Props {
  session: JoinableSession;
  webp?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  webp: undefined,
});

const { t } = useI18n();
const { joinStream } = useJoinStreamConfirm();

const title = computed(() => props.session.rom_name ?? "");

// The listing carries only the cover slice of the ROM; the rest of the
// cover chain (alt art, video) is left empty on purpose.
const coverRom = computed<CoverArtRom>(() => ({
  ss_metadata: null,
  gamelist_metadata: null,
  path_cover_large: props.session.path_cover_large ?? "",
  path_cover_small: props.session.path_cover_small ?? "",
  url_cover: props.session.url_cover ?? "",
  path_video: null,
  platform_slug: props.session.platform ?? "",
}));

const hostLabel = computed(() =>
  props.session.host_username
    ? t("home.live-session-host", { user: props.session.host_username })
    : t("home.live-session-host-unknown"),
);

// Mirrors hostLabel's fallback, so an unknown host reads the same way here
// as it does in the visible meta line, not as "Join 's session".
const joinAriaLabel = computed(() =>
  props.session.host_username
    ? t("rom.join-session-of", { user: props.session.host_username })
    : t("rom.join-session"),
);

async function join(): Promise<void> {
  const romId = props.session.rom_id;
  if (romId == null) return;
  await joinStream({
    romId,
    romName: title.value,
    hostUsername: props.session.host_username,
  });
}
</script>

<template>
  <button
    type="button"
    class="r-live-card"
    :data-focus-key="`live-session-${session.container}`"
    :aria-label="joinAriaLabel"
    @click="join"
  >
    <div class="r-live-card__cover">
      <GameCover :rom="coverRom" :title="title" :webp="webp" morph-static />
      <RChip
        class="r-live-card__live"
        size="small"
        variant="flat"
        color="danger"
        label
      >
        <RIcon icon="mdi-access-point" size="14" />
        {{ t("home.live-session-live") }}
      </RChip>
      <div class="r-live-card__join">
        <RIcon icon="mdi-account-multiple-plus" size="18" />
        <span>{{ t("rom.join-session") }}</span>
      </div>
    </div>
    <div class="r-live-card__name">{{ title }}</div>
    <div class="r-live-card__meta">
      <span>{{ hostLabel }}</span>
      <span v-if="session.platform_display_name" class="r-live-card__platform">
        {{ session.platform_display_name }}
      </span>
    </div>
  </button>
</template>

<style scoped>
.r-live-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 150px;
  flex-shrink: 0;
  padding: 0;
  border: 0;
  background: none;
  color: var(--r-color-fg);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.r-live-card__cover {
  position: relative;
  aspect-ratio: 2 / 3;
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  box-shadow:
    var(--r-elev-1),
    0 0 0 2px color-mix(in srgb, var(--r-color-danger) 70%, transparent);
  transition:
    transform var(--r-motion-fast),
    box-shadow var(--r-motion-fast);
}

.r-live-card__live {
  position: absolute;
  top: 8px;
  left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--r-font-weight-bold);
}

.r-live-card__live :deep(.r-icon) {
  animation: r-live-pulse 1.6s ease-in-out infinite;
}

@keyframes r-live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-live-card__live :deep(.r-icon) {
    animation: none;
  }
}

.r-live-card__join {
  position: absolute;
  inset: auto 0 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: color-mix(
    in srgb,
    var(--r-color-overlay-scrim-strong) 92%,
    transparent
  );
  color: var(--r-color-overlay-fg);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  opacity: 0;
  transform: translateY(100%);
  transition:
    opacity var(--r-motion-fast),
    transform var(--r-motion-fast);
}

html[data-input="mouse"] .r-live-card:hover .r-live-card__cover,
html[data-input="touch"] .r-live-card:hover .r-live-card__cover,
.r-live-card:focus-visible .r-live-card__cover {
  transform: scale(1.05);
  box-shadow:
    var(--r-elev-3),
    0 0 0 2px var(--r-color-danger);
}

html[data-input="mouse"] .r-live-card:hover .r-live-card__join,
html[data-input="touch"] .r-live-card:hover .r-live-card__join,
.r-live-card:focus-visible .r-live-card__join {
  opacity: 1;
  transform: translateY(0);
}

.r-live-card:focus-visible {
  outline: none;
}
.r-live-card:focus-visible .r-live-card__cover {
  box-shadow:
    0 8px 28px color-mix(in srgb, black 40%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
}

.r-live-card__name {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.r-live-card__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
</style>
