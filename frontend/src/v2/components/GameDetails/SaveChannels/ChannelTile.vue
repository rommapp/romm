<script setup lang="ts">
import { RChip, RIcon, RImg } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { ChannelSchema, SaveSchema } from "@/__generated__";
import { formatRelativeDate } from "@/utils";
import { useDeviceLabel } from "@/v2/composables/useDeviceLabel";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  channel: ChannelSchema;
  /** Saves older clients filed under the channel without a snapshot. */
  legacySaves: SaveSchema[];
}>();

const emit = defineEmits<{ open: [] }>();

const { t } = useI18n();
const deviceLabel = useDeviceLabel();

const current = computed(() => props.channel.current);
const newestLegacy = computed(() => props.legacySaves[0] ?? null);
const depth = computed(() =>
  current.value ? props.channel.snapshot_count : props.legacySaves.length,
);
const thumbnail = computed(
  () =>
    current.value?.thumbnail?.download_path ??
    newestLegacy.value?.screenshot?.download_path,
);
const countLabel = computed(() =>
  current.value
    ? t("channels.snapshots-n", depth.value, { named: { n: depth.value } })
    : t("channels.saves-n", depth.value, { named: { n: depth.value } }),
);
const subtitle = computed(() => {
  if (current.value) {
    return [
      formatRelativeDate(current.value.created_at),
      deviceLabel(current.value.device),
    ].join(" · ");
  }
  if (newestLegacy.value)
    return formatRelativeDate(newestLegacy.value.updated_at);
  return t("channels.empty");
});
</script>

<template>
  <button
    type="button"
    class="r-channel-tile"
    v-bind="$attrs"
    :aria-label="t('channels.open-named', { label: channel.label })"
    @click="emit('open')"
  >
    <span class="r-channel-tile__stack" aria-hidden="true">
      <span
        v-if="depth > 2"
        class="r-channel-tile__sheet r-channel-tile__sheet--2"
      />
      <span
        v-if="depth > 1"
        class="r-channel-tile__sheet r-channel-tile__sheet--1"
      />
      <RImg
        v-if="thumbnail"
        class="r-channel-tile__thumb"
        :src="thumbnail"
        cover
        aspect-ratio="4/3"
      />
      <span v-else class="r-channel-tile__thumb r-channel-tile__thumb--empty">
        <RIcon icon="mdi-content-save-outline" size="32" />
      </span>
      <span v-if="depth > 0" class="r-channel-tile__count">{{
        countLabel
      }}</span>
    </span>
    <span class="r-channel-tile__title">
      <span class="r-channel-tile__label">{{ channel.label }}</span>
      <RChip v-if="channel.is_hardcore" size="x-small" color="warning">
        {{ t("channels.hardcore") }}
      </RChip>
      <RChip v-if="channel.is_public" size="x-small" color="success">
        {{
          channel.is_own
            ? t("channels.shared")
            : t("channels.by-owner", { owner: channel.owner_username })
        }}
      </RChip>
      <RChip v-if="!current && depth > 0" size="x-small" variant="outlined">
        {{ t("channels.no-snapshots") }}
      </RChip>
    </span>
    <span class="r-channel-tile__subtitle">{{ subtitle }}</span>
  </button>
</template>

<style scoped>
.r-channel-tile {
  appearance: none;
  background: none;
  border: 0;
  padding: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  min-width: 0;
}
.r-channel-tile__stack {
  position: relative;
  display: block;
  aspect-ratio: 4 / 3;
  max-width: 100%;
}
.r-channel-tile__sheet,
.r-channel-tile__thumb {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border-radius: var(--r-radius-lg);
}
.r-channel-tile__sheet {
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-border-strong);
}
.r-channel-tile__sheet--1 {
  transform: translate(6px, -6px) rotate(2deg);
}
.r-channel-tile__sheet--2 {
  transform: translate(12px, -11px) rotate(4deg);
}
.r-channel-tile__thumb {
  overflow: hidden;
  box-shadow: var(--r-elev-2);
  transition: filter var(--r-motion-fast);
}
.r-channel-tile__thumb--empty {
  display: grid;
  place-items: center;
  background: var(--r-color-surface);
  border: 1px dashed var(--r-color-border-strong);
  color: var(--r-color-fg-muted);
  box-shadow: none;
}
.r-channel-tile:hover .r-channel-tile__thumb {
  filter: brightness(1.06);
}
.r-channel-tile__count {
  position: absolute;
  right: var(--r-space-2);
  bottom: var(--r-space-2);
  padding: 2px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-overlay-scrim-strong);
  color: var(--r-color-overlay-fg);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}
.r-channel-tile__title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-1);
}
.r-channel-tile__label {
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  overflow-wrap: anywhere;
}
.r-channel-tile__subtitle {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
</style>
