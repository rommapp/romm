<script setup lang="ts">
// RandomPickWidget — picks a random ROM from the library and surfaces
// it on the Home dashboard. Body: cover + name + "Open" CTA. Reroll
// button in the card's top-right action slot reshuffles without
// navigating. Two API calls per pick: one to learn the library total,
// one to fetch the selected offset; same approach the v1 RandomBtn
// uses. The pick is intentionally not cached so each mount re-shuffles.
import { RIcon, RImg } from "@v2/lib";
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import { getMissingCoverImage } from "@/utils/covers";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import WidgetCard from "./WidgetCard.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const router = useRouter();
const { toWebp } = useWebpSupport();

const pick = ref<SimpleRom | null>(null);
const loading = ref(false);

async function reroll() {
  loading.value = true;
  try {
    // First call: get the library total. limit=1/offset=0 is cheap and
    // gives us the `total` we need to pick a random offset from.
    const { data: head } = await romApi.getRoms({ limit: 1, offset: 0 });
    if (!head.total || head.total === 0) {
      pick.value = null;
      return;
    }
    const randomOffset = Math.floor(Math.random() * head.total);
    const { data: result } = await romApi.getRoms({
      limit: 1,
      offset: randomOffset,
    });
    pick.value = result.items[0] ?? null;
  } catch {
    pick.value = null;
  } finally {
    loading.value = false;
  }
}

function coverFor(rom: SimpleRom): string {
  if (rom.path_cover_small) return toWebp(rom.path_cover_small);
  return getMissingCoverImage(rom.name || rom.fs_name);
}

function openPick() {
  if (!pick.value) return;
  router.push({ name: ROUTES.ROM, params: { rom: pick.value.id } });
}

onMounted(reroll);
</script>

<template>
  <WidgetCard :title="t('home.widget-random-pick')" :loading="loading">
    <div v-if="pick" class="r-v2-widget-pick__body">
      <RImg
        :src="coverFor(pick)"
        :alt="pick.name || pick.fs_name"
        :width="52"
        :height="70"
        cover
        class="r-v2-widget-pick__cover"
      />
      <div class="r-v2-widget-pick__info">
        <div class="r-v2-widget-pick__name">
          {{ pick.name || pick.fs_name }}
        </div>
        <!-- Open + reroll sit together at the bottom of the info
             column — paired controls read as one cluster instead of
             scattering the reroll up in the card's top-right action
             slot. -->
        <div class="r-v2-widget-pick__actions">
          <button
            type="button"
            class="r-v2-widget-pick__open"
            @click="openPick"
          >
            <RIcon icon="mdi-open-in-new" size="12" />
            <span>{{ t("home.widget-random-pick-open") }}</span>
          </button>
          <button
            type="button"
            class="r-v2-widget-pick__reroll"
            :title="t('home.widget-random-pick-reroll')"
            :aria-label="t('home.widget-random-pick-reroll')"
            @click="reroll"
          >
            <RIcon icon="mdi-dice-multiple-outline" size="14" />
          </button>
        </div>
      </div>
    </div>
    <div v-else class="r-v2-widget-pick__empty">
      {{ t("home.widget-random-pick-empty") }}
    </div>
  </WidgetCard>
</template>

<style scoped>
.r-v2-widget-pick__body {
  display: flex;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.r-v2-widget-pick__cover {
  flex-shrink: 0;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
}

.r-v2-widget-pick__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.r-v2-widget-pick__name {
  font-size: 12.5px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  /* Clamp at 2 lines — random covers + 70px height keep the card from
     growing when the picked title is long. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.r-v2-widget-pick__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: auto;
}

.r-v2-widget-pick__open,
.r-v2-widget-pick__reroll {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: 6px;
  cursor: pointer;
  color: var(--r-color-fg);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-widget-pick__open:hover,
.r-v2-widget-pick__reroll:hover {
  background: var(--r-color-surface-hover);
}

.r-v2-widget-pick__open {
  gap: 5px;
  padding: 4px 10px;
  font-size: 11.5px;
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-widget-pick__reroll {
  width: 26px;
  height: 26px;
  color: var(--r-color-fg-secondary);
}
.r-v2-widget-pick__reroll:hover {
  color: var(--r-color-fg);
}

.r-v2-widget-pick__empty {
  font-size: 12px;
  color: var(--r-color-fg-faint);
  margin-top: auto;
}
</style>
