<script setup lang="ts">
// RandomPickWidget — picks a random ROM from the library and surfaces
// it on the Home dashboard. Body: cover + name + an "Open" / reroll
// button pair. Reroll reshuffles in place without navigating. Two API
// calls per pick: one to learn the library total, one to fetch the
// selected offset; same approach the v1 RandomBtn uses. The pick is
// intentionally not cached so each mount re-shuffles.
import { RBtn, RImg } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import { useCoverArt } from "@/v2/composables/useCoverArt";
import { coverPlaceholderArt } from "@/v2/utils/covers";
import WidgetCard from "./WidgetCard.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const router = useRouter();

const pick = ref<SimpleRom | null>(null);
const loading = ref(false);

// Honour the chosen boxart style here too — the picked cover matches the
// gallery. `useCoverArt` resolves the styled art + webp; we fall back to
// the generated placeholder when the rom has no cover at all.
const art = useCoverArt(() => pick.value);
const coverSrc = computed(() => {
  const r = pick.value;
  if (!r) return "";
  return (
    art.coverUrl.value ??
    art.fallbackUrl.value ??
    coverPlaceholderArt(r.name || r.fs_name, r.is_identified)
  );
});
const coverContain = computed(() => art.objectFit.value === "contain");

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
        :src="coverSrc"
        :alt="pick.name || pick.fs_name"
        :width="52"
        :height="70"
        :cover="!coverContain"
        :contain="coverContain"
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
          <RBtn
            variant="outlined"
            surface
            size="x-small"
            prepend-icon="mdi-open-in-new"
            @click="openPick"
          >
            {{ t("home.widget-random-pick-open") }}
          </RBtn>
          <RBtn
            variant="outlined"
            surface
            size="x-small"
            icon="mdi-dice-multiple-outline"
            :tooltip="t('home.widget-random-pick-reroll')"
            :aria-label="t('home.widget-random-pick-reroll')"
            @click="reroll"
          />
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

.r-v2-widget-pick__empty {
  font-size: 12px;
  color: var(--r-color-fg-faint);
  margin-top: auto;
}
</style>
