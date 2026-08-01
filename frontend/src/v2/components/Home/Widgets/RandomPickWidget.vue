<script setup lang="ts">
// RandomPickWidget — picks a random ROM from the library and surfaces
// it on the Home dashboard. Body: cover + name + platform + release
// year / region, the whole thing a link to the rom. Reroll lives in
// the card's top-right action slot and reshuffles in place without
// navigating. Two API calls per pick: one to learn the library total,
// one to fetch the selected offset; same approach the v1 RandomBtn
// uses. The pick is intentionally not cached so each mount re-shuffles.
import { RBtn, RChip } from "@v2/lib";
import { computed, nextTick, onMounted, ref } from "vue";
import type { ComponentPublicInstance } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import WidgetCard from "./WidgetCard.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const snackbar = useSnackbar();

// The reroll button shows a real die face rather than the stacked
// `dice-multiple` glyph, which reads as two windows at this size. Each
// roll lands on a different face.
const DICE_FACES = [
  "mdi-dice-1-outline",
  "mdi-dice-2-outline",
  "mdi-dice-3-outline",
  "mdi-dice-4-outline",
  "mdi-dice-5-outline",
  "mdi-dice-6-outline",
];

// A pick needs a single row, so it opts out of the char index, filter
// values and rom id index the endpoint returns by default: each of them
// spans the whole library and dwarfs the row itself.
const PICK_QUERY = {
  limit: 1,
  withCharIndex: false,
  withFilterValues: false,
  withRomIdIndex: false,
} as const;

const pick = ref<SimpleRom | null>(null);
const loading = ref(false);
const failed = ref(false);
const diceFace = ref(DICE_FACES[Math.floor(Math.random() * DICE_FACES.length)]);
const rerollBtn = ref<ComponentPublicInstance | null>(null);

function rerollEl(): HTMLElement | null {
  return (rerollBtn.value?.$el as HTMLElement | undefined) ?? null;
}

const title = computed(() => pick.value?.name || pick.value?.fs_name || "");

const releaseYear = computed(() => {
  const ts = pick.value?.metadatum?.first_release_date;
  if (!ts) return null;
  const date = new Date(Number(ts));
  return Number.isNaN(date.getTime()) ? null : date.getFullYear();
});

const region = computed(() => pick.value?.regions?.[0] ?? null);

const placeholder = computed(() =>
  failed.value
    ? t("home.widget-random-pick-error")
    : t("home.widget-random-pick-empty"),
);

function rollDiceFace() {
  const others = DICE_FACES.filter((face) => face !== diceFace.value);
  diceFace.value = others[Math.floor(Math.random() * others.length)];
}

// One attempt at a pick. `null` means the library holds no roms;
// `undefined` means the offset came back empty, which the backend's
// cached id index makes possible when it drifts from the database
// between the two calls (a scan, a deletion).
async function pickOnce(): Promise<SimpleRom | null | undefined> {
  const { data: head } = await romApi.getRoms({ ...PICK_QUERY, offset: 0 });
  if (!head.total) return null;

  const { data: result } = await romApi.getRoms({
    ...PICK_QUERY,
    offset: Math.floor(Math.random() * head.total),
  });
  return result.items.at(0);
}

async function reroll({ notify }: { notify: boolean }) {
  if (loading.value) return;
  rollDiceFace();
  // Disabling the button pulls focus to <body>; hand it back after.
  const hadFocus = document.activeElement === rerollEl();
  loading.value = true;
  try {
    let rom = await pickOnce();
    // Drift is worth one retry, since the second attempt re-reads the total.
    if (rom === undefined) rom = await pickOnce();
    if (rom === undefined) throw new Error("random pick came back empty");
    pick.value = rom;
    failed.value = false;
  } catch {
    // Keep the previous pick: a failed request says nothing about whether
    // the library holds games, so falling back to the empty copy would lie.
    failed.value = true;
    if (notify) snackbar.error(t("home.widget-random-pick-error"));
  } finally {
    loading.value = false;
    if (hadFocus) {
      await nextTick();
      rerollEl()?.focus();
    }
  }
}

function onReroll() {
  void reroll({ notify: true });
}

// The first pick is ours, not the user's: the card carries its own
// failure copy, so it stays out of the snackbar stack.
onMounted(() => reroll({ notify: false }));
</script>

<template>
  <WidgetCard :title="t('home.widget-random-pick')" :loading="loading">
    <template #action>
      <RBtn
        ref="rerollBtn"
        variant="text"
        size="small"
        :icon="diceFace"
        :disabled="loading"
        class="r-v2-widget-pick__reroll"
        :tooltip="t('home.widget-random-pick-reroll')"
        :aria-label="t('home.widget-random-pick-reroll')"
        @click="onReroll"
      />
    </template>
    <router-link
      v-if="pick"
      class="r-v2-widget-pick__body"
      :to="{ name: ROUTES.ROM, params: { rom: pick.id } }"
    >
      <GameCover
        :rom="pick"
        :title="title"
        :identified="pick.is_identified"
        class="r-v2-widget-pick__cover"
      />
      <div class="r-v2-widget-pick__info">
        <div class="r-v2-widget-pick__name">{{ title }}</div>
        <div class="r-v2-widget-pick__platform">
          <CachedPlatformIcon
            :slug="pick.platform_slug"
            :name="pick.platform_display_name"
            :size="14"
          />
          <span class="r-v2-widget-pick__platform-name">
            {{ pick.platform_display_name }}
          </span>
        </div>
        <!-- Year + region disambiguate the pick when a library holds
             several variations of the same title. -->
        <div v-if="releaseYear || region" class="r-v2-widget-pick__meta">
          <span v-if="releaseYear">{{ releaseYear }}</span>
          <RChip v-if="region" size="x-small" variant="translucent">
            {{ region }}
          </RChip>
        </div>
      </div>
    </router-link>
    <div v-else class="r-v2-widget-pick__empty">
      {{ placeholder }}
    </div>
  </WidgetCard>
</template>

<style scoped>
.r-v2-widget-pick__body {
  display: flex;
  gap: 10px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-decoration: none;
  border-radius: var(--r-radius-sm);
}

/* Fixed height, natural width — the cover renders at its image's true
   aspect (GameCover measures it), matching the gallery. The descendant
   selector outweighs GameCover's base `width: 100%` so width can follow
   the ratio. */
.r-v2-widget-pick__body .r-v2-widget-pick__cover {
  height: 70px;
  width: auto;
  flex-shrink: 0;
  --r-cover-radius: var(--r-radius-sm);
}

.r-v2-widget-pick__info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-v2-widget-pick__name {
  font-size: 12.5px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.2;
  color: var(--r-color-fg);
  /* Clamp at 2 lines — random covers + 70px height keep the card from
     growing when the picked title is long. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Hover is gated to pointer modalities so a parked cursor doesn't
   compete with the focused element under keyboard / gamepad. */
html[data-input="mouse"] .r-v2-widget-pick__body:hover .r-v2-widget-pick__name,
html[data-input="touch"] .r-v2-widget-pick__body:hover .r-v2-widget-pick__name,
.r-v2-widget-pick__body:focus-visible .r-v2-widget-pick__name {
  color: var(--r-color-brand-primary);
}

.r-v2-widget-pick__platform {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-v2-widget-pick__platform-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-widget-pick__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: auto;
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

/* The die reads as a die only above the button's default 1.25em glyph. */
.r-v2-widget-pick__reroll :deep(.r-btn__icon) {
  font-size: 19px;
}

.r-v2-widget-pick__empty {
  font-size: 12px;
  color: var(--r-color-fg-faint);
  margin-top: auto;
}
</style>
