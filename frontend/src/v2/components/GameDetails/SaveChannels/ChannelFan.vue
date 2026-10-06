<script setup lang="ts">
import { RBtn, RMenu, RMenuItem, RSkeletonBlock } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type {
  ChannelSchema,
  SaveSchema,
  SnapshotSchema,
} from "@/__generated__";
import { formatRelativeDate } from "@/utils";
import SnapshotCard, {
  type CardBadge,
} from "@/v2/components/GameDetails/SaveChannels/SnapshotCard.vue";
import { useDeviceLabel } from "@/v2/composables/useDeviceLabel";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    channel: ChannelSchema;
    /** Newest first; null while the first page loads. */
    history: SnapshotSchema[] | null;
    legacySaves: SaveSchema[];
    hasMore?: boolean;
    loadingMore?: boolean;
  }>(),
  { hasMore: false, loadingMore: false },
);

const emit = defineEmits<{
  collapse: [];
  openSnapshot: [snapshot: SnapshotSchema];
  openSave: [save: SaveSchema];
  rename: [];
  toggleShare: [];
  delete: [];
  loadMore: [];
}>();

const { t } = useI18n();
const deviceLabel = useDeviceLabel();

const spread = ref(false);
onMounted(() => requestAnimationFrame(() => (spread.value = true)));

function badgesFor(snapshot: SnapshotSchema): CardBadge[] {
  const badges: CardBadge[] = [];
  if (snapshot.id === props.channel.current_snapshot_id) {
    badges.push({ label: t("channels.current"), color: "primary" });
  }
  if (snapshot.kind === "branch") {
    badges.push({ label: t("channels.branch"), outlined: true });
  }
  if (snapshot.is_pinned) {
    badges.push({ label: t("channels.pinned"), color: "accent" });
  }
  if (snapshot.is_hardcore) {
    badges.push({ label: t("channels.hardcore"), color: "warning" });
  }
  return badges;
}

const cardCount = computed(
  () => (props.history?.length ?? 0) + props.legacySaves.length,
);
</script>

<template>
  <section
    class="r-channel-fan"
    v-bind="$attrs"
    :aria-label="t('channels.open-named', { label: channel.label })"
  >
    <header class="r-channel-fan__head">
      <h4 class="r-channel-fan__title">{{ channel.label }}</h4>
      <div class="r-channel-fan__actions">
        <RMenu v-if="channel.is_own" location="bottom end" :offset="6">
          <template #activator="{ props: activatorProps }">
            <RBtn
              v-bind="activatorProps"
              icon="mdi-dots-vertical"
              variant="text"
              size="small"
              :aria-label="t('rom.more-actions')"
              :tooltip="t('rom.more-actions')"
            />
          </template>
          <RMenuItem
            :label="t('channels.rename')"
            icon="mdi-pencil-outline"
            @click="emit('rename')"
          />
          <RMenuItem
            :label="
              channel.is_public
                ? t('channels.stop-sharing')
                : t('channels.share')
            "
            :icon="channel.is_public ? 'mdi-earth-off' : 'mdi-earth'"
            @click="emit('toggleShare')"
          />
          <RMenuItem
            :label="t('channels.delete')"
            icon="mdi-delete-outline"
            variant="danger"
            @click="emit('delete')"
          />
        </RMenu>
        <RBtn
          icon="mdi-chevron-up"
          variant="text"
          size="small"
          :aria-label="t('channels.collapse')"
          :tooltip="t('channels.collapse')"
          @click="emit('collapse')"
        />
      </div>
    </header>

    <div v-if="history === null" class="r-channel-fan__cards">
      <RSkeletonBlock
        v-for="n in 3"
        :key="n"
        class="r-channel-fan__skeleton"
        width="168px"
        height="200px"
        rounded="lg"
      />
    </div>
    <div
      v-else
      class="r-channel-fan__cards"
      :class="{ 'r-channel-fan__cards--spread': spread }"
    >
      <SnapshotCard
        v-for="(snapshot, index) in history"
        :key="`s-${snapshot.id}`"
        class="r-channel-fan__card"
        :style="{
          '--r-fan-index': index,
          zIndex: cardCount - index,
        }"
        :title="formatRelativeDate(snapshot.created_at)"
        :subtitle="deviceLabel(snapshot.device)"
        :caption="`#${snapshot.id}`"
        :thumbnail="snapshot.thumbnail?.download_path"
        :badges="badgesFor(snapshot)"
        :current="snapshot.id === channel.current_snapshot_id"
        :muted="snapshot.kind === 'branch'"
        @open="emit('openSnapshot', snapshot)"
      />
      <SnapshotCard
        v-for="(save, index) in legacySaves"
        :key="`l-${save.id}`"
        class="r-channel-fan__card"
        :style="{
          '--r-fan-index': history.length + index,
          zIndex: legacySaves.length - index,
        }"
        :title="formatRelativeDate(save.updated_at)"
        :subtitle="save.file_name"
        :thumbnail="save.screenshot?.download_path"
        :badges="[{ label: t('channels.legacy-save'), outlined: true }]"
        muted
        @open="emit('openSave', save)"
      />
      <RBtn
        v-if="hasMore"
        class="r-channel-fan__more"
        variant="outlined"
        size="small"
        :loading="loadingMore"
        @click="emit('loadMore')"
      >
        {{ t("channels.load-more") }}
      </RBtn>
    </div>
  </section>
</template>

<style scoped>
.r-channel-fan {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding: var(--r-space-4);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  min-width: 0;
}
.r-channel-fan__head {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
}
.r-channel-fan__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-channel-fan__actions {
  display: flex;
  flex: none;
  gap: var(--r-space-1);
}
.r-channel-fan__cards {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding: 6px 4px 12px;
  scroll-snap-type: x proximity;
}
.r-channel-fan__card,
.r-channel-fan__skeleton {
  flex: 0 0 168px;
  align-self: start;
  scroll-snap-align: start;
}
.r-channel-fan__card:first-child {
  flex-basis: 220px;
}
.r-channel-fan__card {
  position: relative;
  transform: translateX(calc(var(--r-fan-index) * -182px))
    rotate(
      calc(min(var(--r-fan-index), 1) * (2deg + var(--r-fan-index) * 1deg))
    );
  transition: transform 380ms var(--r-motion-ease-out);
  transition-delay: calc(var(--r-fan-index) * 40ms);
}
.r-channel-fan__cards--spread .r-channel-fan__card {
  transform: none;
}
.r-channel-fan__more {
  align-self: center;
  flex: none;
}
@media (prefers-reduced-motion: reduce) {
  .r-channel-fan__card {
    transition: none;
  }
}
</style>
