<script setup lang="ts">
// SaveDataPanel: the save-archive half of the streaming launch screen's
// resume panel. It stands alone where the emulator has no save states,
// and sits behind a tab alongside the state picker where it has both.
//
// The save is reported, never offered. Nothing here is clickable and the
// word "resume" is absent: the archive is restored into the emulated
// filesystem before the game boots, so the player still has to load it
// from the game's own menu, and a slot-shaped affordance would promise a
// jump the emulator cannot make.
import { RIcon } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { SaveSchema } from "@/__generated__";
import AssetChips from "@/v2/components/shared/AssetChips.vue";
import AssetTimestamp from "@/v2/components/shared/AssetTimestamp.vue";

defineProps<{
  save: SaveSchema | null;
  platform: string;
}>();

const { t } = useI18n();
</script>

<template>
  <div class="r-v2-save-data">
    <div class="r-v2-save-data__status">
      <span
        class="r-v2-save-data__badge"
        :class="{ 'r-v2-save-data__badge--on': save !== null }"
      >
        <RIcon
          :icon="save ? 'mdi-cloud-check-outline' : 'mdi-cloud-off-outline'"
          size="19"
        />
      </span>
      <div class="r-v2-save-data__text">
        <p class="r-v2-save-data__headline">
          {{ save ? t("play.save-data-synced") : t("play.save-data-none") }}
        </p>
        <div v-if="save" class="r-v2-save-data__facts">
          <AssetChips :asset="save" :show-emulator="false" />
          <AssetTimestamp :date="save.updated_at" />
        </div>
        <p v-else class="r-v2-save-data__detail">
          {{ t("play.save-data-none-hint", { platform }) }}
        </p>
      </div>
    </div>
    <p class="r-v2-save-data__note">
      {{ save ? t("play.save-data-note") : t("play.save-data-none-note") }}
    </p>
  </div>
</template>

<style scoped>
.r-v2-save-data {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-save-data__status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.r-v2-save-data__badge {
  flex: none;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
}
.r-v2-save-data__badge--on {
  background: color-mix(in srgb, var(--r-color-brand-primary) 16%, transparent);
  color: var(--r-color-brand-primary);
}

.r-v2-save-data__text {
  min-width: 0;
}
.r-v2-save-data__headline {
  margin: 0;
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg);
}
.r-v2-save-data__facts {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  margin-top: 4px;
}
.r-v2-save-data__detail {
  margin: 2px 0 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-save-data__note {
  margin: 0;
  padding-top: 14px;
  border-top: 1px solid var(--r-color-border);
  font-size: var(--r-font-size-sm);
  line-height: 1.6;
  color: var(--r-color-fg-muted);
}
</style>
