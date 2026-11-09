<script setup lang="ts">
// AchievementsIndex: PlayStation-style trophy list in RomM's skin.
// The library is one row per game (cover, name, platform, completion).
// Opening a game keeps the RetroAchievements icon beside the name and paints
// that ROM's cover on the shared backdrop. Counts are RetroAchievements
// types and points. Metals are not invented.
import { useEventListener } from "@vueuse/core";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import IndexShell from "@/components/shared/IndexShell.vue";
import PageHeader from "@/components/shared/PageHeader.vue";
import PlatformIcon from "@/components/shared/PlatformIcon.vue";
import { useBackgroundArt } from "@/composables/useBackgroundArt";
import { useGridNav } from "@/composables/useGridNav";
import { useLoadingPhase } from "@/composables/useLoadingPhase";
import {
  pendingMorphName,
  useViewTransition,
} from "@/composables/useViewTransition";
import { useWebpSupport } from "@/composables/useWebpSupport";
import {
  RBtn,
  RChip,
  REmptyState,
  RIcon,
  RImage,
  RSelect,
  RSkeletonBlock,
} from "@/lib";
import { ROUTES } from "@/plugins/router";
import {
  type AchievementGame,
  type AchievementTypeCounts,
  type CatalogAchievement,
  useEarnedAchievementsState,
} from "@/services/api/user";
import storeAuth from "@/stores/auth";

const TYPE_COLUMNS = [
  {
    key: "progression",
    icon: "mdi-flag-checkered",
    label: "rom.achievements-type-progression",
  },
  {
    key: "missable",
    icon: "mdi-alert-outline",
    label: "rom.achievements-type-missable",
  },
  {
    key: "win_condition",
    icon: "mdi-crown-outline",
    label: "rom.achievements-type-win-condition",
  },
  {
    key: "other",
    icon: "mdi-trophy-outline",
    label: "achievements.sort-other",
  },
] as const;

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const authStore = storeAuth();
const setBgArt = useBackgroundArt();
const { toWebp } = useWebpSupport();
const { morphTransition } = useViewTransition();

const { loading, refreshing, failed, payload, load } =
  useEarnedAchievementsState();
const gridRoot = ref<HTMLElement | null>(null);
useGridNav(gridRoot, { cellSelector: ".r-v2-ach__row" });
const sortKey = ref("catalog");
const brokenCovers = ref<Record<number, true>>({});
const remoteArt = ref<Record<string, true>>({});
const brokenArt = ref<Record<string, true>>({});

const games = computed(() => payload.value?.games ?? []);
const linked = computed(() => payload.value?.linked === true);
const synced = computed(() => payload.value?.synced === true);
const phase = useLoadingPhase(
  loading,
  () => !failed.value && games.value.length === 0,
);

const selectedId = computed(() => {
  const raw = route.query.rom;
  const value = Array.isArray(raw) ? raw[0] : raw;
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
});

const selectedGame = computed(
  () => games.value.find((game) => game.rom_id === selectedId.value) ?? null,
);

function gameBackdrop(game: AchievementGame | null) {
  if (!game) return null;
  const local = game.path_cover_large || game.path_cover_small;
  if (local) return toWebp(local);
  return game.url_cover || game.cover_url || null;
}

watch(
  () => gameBackdrop(selectedGame.value),
  (url) => {
    if (url) setBgArt(url);
  },
  { immediate: true },
);

const profileTo = computed(() =>
  authStore.user
    ? { name: ROUTES.USER_PROFILE, params: { user: authStore.user.id } }
    : undefined,
);

const sortItems = computed(() => [
  { title: t("achievements.sort-catalog"), value: "catalog" },
  { title: t("achievements.points-label"), value: "points" },
  { title: t("common.type"), value: "type" },
  { title: t("achievements.sort-date"), value: "date" },
]);

const visibleAchievements = computed(() => {
  const game = selectedGame.value;
  if (!game) return [];
  const list = [...game.achievements];
  const byTitle = (item: CatalogAchievement) =>
    (item.title ?? "").toLocaleLowerCase();
  if (sortKey.value === "points") {
    list.sort(
      (a, b) =>
        (b.points ?? -1) - (a.points ?? -1) ||
        byTitle(a).localeCompare(byTitle(b)),
    );
  } else if (sortKey.value === "type") {
    list.sort(
      (a, b) =>
        typeRank(a) - typeRank(b) || byTitle(a).localeCompare(byTitle(b)),
    );
  } else if (sortKey.value === "date") {
    list.sort((a, b) => {
      if (a.earned_at && b.earned_at) {
        return a.earned_at < b.earned_at
          ? 1
          : a.earned_at > b.earned_at
            ? -1
            : 0;
      }
      if (a.earned_at) return -1;
      if (b.earned_at) return 1;
      return byTitle(a).localeCompare(byTitle(b));
    });
  } else {
    list.sort((a, b) => {
      const ao = a.display_order;
      const bo = b.display_order;
      if (ao != null && bo != null && ao !== bo) return ao - bo;
      if (ao != null && bo == null) return -1;
      if (ao == null && bo != null) return 1;
      return 0;
    });
  }
  return list;
});

watch(selectedId, () => {
  sortKey.value = "catalog";
});

watch([selectedId, games, loading, refreshing], () => {
  if (loading.value || refreshing.value || selectedId.value == null) return;
  if (!games.value.some((game) => game.rom_id === selectedId.value)) {
    void router.replace({ name: ROUTES.ACHIEVEMENTS });
  }
});

function completionPercent(earned: number, total: number) {
  if (total <= 0 || earned <= 0) return 0;
  if (earned >= total) return 100;
  return Math.round((earned * 100) / total);
}

function formatCount(value: number) {
  return new Intl.NumberFormat(locale.value.replaceAll("_", "-")).format(value);
}

function typeRank(item: CatalogAchievement) {
  if (item.type === "win_condition") return 0;
  if (item.type === "progression") return 1;
  if (item.type === "missable") return 2;
  return 3;
}

function achievementTypeLabel(type: string | null) {
  switch (type) {
    case "progression":
      return t("rom.achievements-type-progression");
    case "missable":
      return t("rom.achievements-type-missable");
    case "win_condition":
      return t("rom.achievements-type-win-condition");
    default:
      return null;
  }
}

function artKey(item: CatalogAchievement) {
  return `${item.id}:${item.earned ? "on" : "off"}`;
}

function artSrc(item: CatalogAchievement) {
  const path = item.earned
    ? item.badge_path
    : (item.badge_path_lock ?? item.badge_path);
  const url = item.earned
    ? item.badge_url
    : (item.badge_url_lock ?? item.badge_url);
  if (!remoteArt.value[artKey(item)] && path) return path;
  return url ?? "";
}

function showArt(item: CatalogAchievement) {
  return Boolean(artSrc(item)) && !brokenArt.value[artKey(item)];
}

function onArtError(item: CatalogAchievement) {
  const key = artKey(item);
  const path = item.earned
    ? item.badge_path
    : (item.badge_path_lock ?? item.badge_path);
  const url = item.earned
    ? item.badge_url
    : (item.badge_url_lock ?? item.badge_url);
  if (path && url && !remoteArt.value[key]) {
    remoteArt.value = { ...remoteArt.value, [key]: true };
    return;
  }
  brokenArt.value = { ...brokenArt.value, [key]: true };
}

function achievementIconName(romId: number) {
  return `ach-icon-${romId}`;
}

function openGame(game: AchievementGame, cover?: HTMLElement | null) {
  const go = async () => {
    await router.push({
      name: ROUTES.ACHIEVEMENTS,
      query: { rom: String(game.rom_id) },
    });
    window.scrollTo(0, 0);
  };
  if (cover) {
    morphTransition({ el: cover, name: achievementIconName(game.rom_id) }, go);
    return;
  }
  void go();
}

function onRowClick(event: MouseEvent, game: AchievementGame) {
  const cover = (event.currentTarget as HTMLElement).querySelector(
    ".r-v2-ach__cover",
  );
  openGame(game, cover instanceof HTMLElement ? cover : null);
}

function counterLabel(
  counts: AchievementTypeCounts,
  key: keyof AchievementTypeCounts,
) {
  const column = TYPE_COLUMNS.find((entry) => entry.key === key);
  return column ? `${t(column.label)} ${counts[key]}` : String(counts[key]);
}

function refreshIfVisible() {
  if (document.visibilityState === "hidden") return;
  void load(true);
}

useEventListener(window, "focus", refreshIfVisible);
useEventListener(document, "visibilitychange", refreshIfVisible);

onMounted(() => {
  void load(payload.value !== null);
});
</script>

<template>
  <IndexShell>
    <template #header>
      <header v-if="selectedGame" class="r-v2-ach__detail-head">
        <div class="r-v2-ach__detail-top">
          <span
            class="r-v2-ach__icon"
            :style="{
              viewTransitionName: achievementIconName(selectedGame.rom_id),
            }"
          >
            <RImage
              v-if="
                selectedGame.cover_url && !brokenCovers[selectedGame.rom_id]
              "
              :src="selectedGame.cover_url"
              alt=""
              width="100%"
              height="100%"
              cover
              @error="
                brokenCovers = { ...brokenCovers, [selectedGame.rom_id]: true }
              "
            >
              <template #loading>
                <RSkeletonBlock width="100%" height="100%" rounded="none" />
              </template>
            </RImage>
            <RIcon v-else icon="mdi-image-outline" :size="22" />
          </span>
          <div class="r-v2-ach__detail-name">
            <h1>{{ selectedGame.name }}</h1>
            <RChip
              v-if="selectedGame.platform_name"
              class="r-v2-ach__platform"
              size="x-small"
              label
              variant="outlined"
            >
              <span class="r-v2-ach__platform-label">
                <PlatformIcon
                  :slug="selectedGame.platform_slug ?? undefined"
                  :fs-slug="selectedGame.platform_fs_slug ?? undefined"
                  :size="14"
                  :alt="selectedGame.platform_name"
                  :show-tooltip="false"
                />
                <span>{{ selectedGame.platform_name }}</span>
              </span>
            </RChip>
          </div>
        </div>
        <div class="r-v2-ach__detail-stats">
          <div class="r-v2-ach__stat">
            <span class="r-v2-ach__k">{{ t("rom.your-progress") }}</span>
            <span class="r-v2-ach__stat-value">
              {{ completionPercent(selectedGame.earned, selectedGame.total) }}%
            </span>
            <span
              class="r-v2-ach__track"
              role="progressbar"
              :aria-valuenow="
                completionPercent(selectedGame.earned, selectedGame.total)
              "
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="t('rom.your-progress')"
            >
              <span
                class="r-v2-ach__fill"
                :style="{
                  width: `${completionPercent(selectedGame.earned, selectedGame.total)}%`,
                }"
              />
            </span>
          </div>
          <div class="r-v2-ach__stat">
            <span class="r-v2-ach__k">{{ t("rom.achievements-earned") }}</span>
            <span class="r-v2-ach__stat-value">
              {{ selectedGame.earned }}/{{ selectedGame.total }}
            </span>
          </div>
          <div class="r-v2-ach__counts">
            <span
              v-for="column in TYPE_COLUMNS"
              :key="column.key"
              class="r-v2-ach__count"
              :class="[
                `r-v2-ach__count--${column.key}`,
                {
                  'r-v2-ach__count--zero':
                    selectedGame.earned_by_type[column.key] === 0,
                },
              ]"
              :title="t(column.label)"
              :aria-label="
                counterLabel(selectedGame.earned_by_type, column.key)
              "
            >
              <RIcon :icon="column.icon" :size="16" />
              <span>{{ selectedGame.earned_by_type[column.key] }}</span>
            </span>
          </div>
        </div>
      </header>

      <div v-else-if="phase === 'content' && payload" class="r-v2-ach__head">
        <PageHeader
          :title="t('common.achievements')"
          class="r-v2-ach__page-title"
        >
          <template #count>
            <div class="r-v2-ach__level">
              <span class="r-v2-ach__medal" aria-hidden="true">
                <RIcon icon="mdi-trophy" :size="18" color="romm-gold" />
              </span>
              <span class="r-v2-ach__level-text">
                <span class="r-v2-ach__level-value">
                  {{ formatCount(payload.points_earned) }}
                </span>
                <span class="r-v2-ach__k">{{
                  t("achievements.points-label")
                }}</span>
              </span>
            </div>
          </template>
        </PageHeader>
        <div class="r-v2-ach__total">
          <span class="r-v2-ach__k">{{ t("achievements.counter-total") }}</span>
          <span class="r-v2-ach__total-value">{{
            formatCount(payload.earned)
          }}</span>
        </div>
        <span
          v-for="column in TYPE_COLUMNS"
          :key="column.key"
          class="r-v2-ach__count r-v2-ach__count--head"
          :class="[
            `r-v2-ach__count--${column.key}`,
            {
              'r-v2-ach__count--zero': payload.earned_by_type[column.key] === 0,
            },
          ]"
          :title="t(column.label)"
          :aria-label="counterLabel(payload.earned_by_type, column.key)"
        >
          <RIcon :icon="column.icon" :size="16" />
          <span>{{ payload.earned_by_type[column.key] }}</span>
        </span>
      </div>

      <h1 v-else class="r-v2-ach__title r-v2-ach__title--solo">
        {{ t("common.achievements") }}
      </h1>
    </template>

    <template v-if="selectedGame" #toolbar>
      <div class="r-v2-ach__toolbar">
        <RSelect
          v-model="sortKey"
          class="r-v2-ach__sort"
          :items="sortItems"
          prefix-label="inline"
          density="compact"
          variant="outlined"
          hide-details
        >
          <template #prefix-label>
            {{ t("gallery.sort-by") }}
          </template>
        </RSelect>
      </div>
    </template>

    <REmptyState
      v-if="failed && phase !== 'skeleton'"
      icon="mdi-trophy-outline"
      :title="t('achievements.load-error')"
    >
      <template #actions>
        <RBtn color="primary" @click="load()">
          {{ t("common.try-again") }}
        </RBtn>
      </template>
    </REmptyState>

    <div v-else-if="phase === 'skeleton'" class="r-v2-ach__skeletons">
      <RSkeletonBlock v-for="n in 6" :key="n" height="72" rounded="md" />
    </div>

    <REmptyState
      v-else-if="phase === 'empty' && !linked"
      icon="mdi-trophy-outline"
      :title="t('achievements.empty-unlinked-title')"
      :hint="t('achievements.empty-unlinked-hint')"
    >
      <template v-if="profileTo" #actions>
        <RBtn
          color="primary"
          prepend-icon="mdi-account-outline"
          :to="profileTo"
        >
          {{ t("achievements.go-to-profile") }}
        </RBtn>
      </template>
    </REmptyState>

    <REmptyState
      v-else-if="phase === 'empty' && !synced"
      icon="mdi-trophy-outline"
      :title="t('achievements.empty-unsynced-title')"
      :hint="t('achievements.empty-unsynced-hint')"
    >
      <template v-if="profileTo" #actions>
        <RBtn
          color="primary"
          prepend-icon="mdi-account-outline"
          :to="profileTo"
        >
          {{ t("achievements.go-to-profile") }}
        </RBtn>
      </template>
    </REmptyState>

    <REmptyState
      v-else-if="phase === 'empty'"
      icon="mdi-trophy-outline"
      :title="t('achievements.empty-earned-title')"
      :hint="t('achievements.empty-earned-hint')"
    />

    <ul v-else-if="selectedGame" class="r-v2-ach__grid">
      <li
        v-for="item in visibleAchievements"
        :key="item.id"
        class="r-v2-ach__card"
        :class="{ 'r-v2-ach__card--locked': !item.earned }"
      >
        <div
          class="r-v2-ach__art"
          :class="{ 'r-v2-ach__art--fallback': !showArt(item) }"
        >
          <RImage
            v-if="showArt(item)"
            :src="artSrc(item)"
            alt=""
            width="100%"
            height="100%"
            contain
            lazy
            @error="onArtError(item)"
          >
            <template #loading>
              <RSkeletonBlock width="100%" height="100%" rounded="none" />
            </template>
          </RImage>
          <RIcon v-else icon="mdi-trophy" :size="36" color="romm-gold" />
          <span v-if="!item.earned" class="r-v2-ach__lock" aria-hidden="true">
            <RIcon icon="mdi-lock" :size="20" />
          </span>
        </div>
        <span v-if="achievementTypeLabel(item.type)" class="r-v2-ach__type">
          {{ achievementTypeLabel(item.type) }}
        </span>
        <span class="r-v2-ach__card-title">{{ item.title }}</span>
        <p v-if="item.description" class="r-v2-ach__card-desc">
          {{ item.description }}
        </p>
      </li>
    </ul>

    <ul v-else-if="phase === 'content'" ref="gridRoot" class="r-v2-ach__games">
      <li v-for="game in games" :key="game.rom_id">
        <button
          type="button"
          class="r-v2-ach__row"
          :data-focus-key="`achievement-${game.rom_id}`"
          @click="onRowClick($event, game)"
        >
          <span class="r-v2-ach__game">
            <span
              class="r-v2-ach__cover"
              :style="
                pendingMorphName === achievementIconName(game.rom_id)
                  ? { viewTransitionName: achievementIconName(game.rom_id) }
                  : undefined
              "
            >
              <RImage
                v-if="game.cover_url && !brokenCovers[game.rom_id]"
                :src="game.cover_url"
                alt=""
                width="100%"
                height="100%"
                contain
                lazy
                @error="brokenCovers = { ...brokenCovers, [game.rom_id]: true }"
              >
                <template #loading>
                  <RSkeletonBlock width="100%" height="100%" rounded="none" />
                </template>
              </RImage>
              <RIcon v-else icon="mdi-image-outline" :size="20" />
            </span>
            <span class="r-v2-ach__game-text">
              <span class="r-v2-ach__game-name">{{ game.name }}</span>
              <RChip
                v-if="game.platform_name"
                class="r-v2-ach__platform"
                size="x-small"
                label
                variant="outlined"
              >
                <span class="r-v2-ach__platform-label">
                  <PlatformIcon
                    :slug="game.platform_slug ?? undefined"
                    :fs-slug="game.platform_fs_slug ?? undefined"
                    :size="14"
                    :alt="game.platform_name"
                    :show-tooltip="false"
                  />
                  <span>{{ game.platform_name }}</span>
                </span>
              </RChip>
            </span>
          </span>
          <span class="r-v2-ach__pct">
            {{ completionPercent(game.earned, game.total) }}%
          </span>
          <span
            v-for="column in TYPE_COLUMNS"
            :key="column.key"
            class="r-v2-ach__count"
            :class="[
              `r-v2-ach__count--${column.key}`,
              {
                'r-v2-ach__count--zero': game.earned_by_type[column.key] === 0,
              },
            ]"
            :title="t(column.label)"
            :aria-label="counterLabel(game.earned_by_type, column.key)"
          >
            <RIcon :icon="column.icon" :size="15" />
            <span>{{ game.earned_by_type[column.key] }}</span>
          </span>
        </button>
      </li>
    </ul>
  </IndexShell>
</template>

<style scoped>
/* Same h1 metrics as PageHeader, so Logros and Colecciones crossfade at one size. */
.r-v2-ach__title {
  margin: 0;
  flex: 0 0 auto;
  font-size: var(--r-font-size-3xl);
  font-weight: var(--r-font-weight-extrabold);
  letter-spacing: -0.025em;
  line-height: var(--r-line-height-tight);
  color: var(--r-color-fg-heading);
}

.r-v2-ach__title--solo {
  padding-bottom: var(--r-space-6);
}

.r-v2-ach__k {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}

.r-v2-ach__head,
.r-v2-ach__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 84px repeat(4, 64px);
  column-gap: var(--r-space-3);
  align-items: center;
}

.r-v2-ach__head {
  /* Same 24px under the title as PageHeader. */
  padding-bottom: 24px;
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-ach__head :deep(.page-header) {
  min-width: 0;
  padding-bottom: 0;
}

.r-v2-ach__head :deep(.page-header__title) {
  flex-shrink: 0;
}

.r-v2-ach__lead {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-5) var(--r-space-7);
  min-width: 0;
}

.r-v2-ach__level,
.r-v2-ach__progress {
  display: flex;
  align-items: center;
  gap: 10px;
}

.r-v2-ach__level-text,
.r-v2-ach__progress,
.r-v2-ach__total,
.r-v2-ach__stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.r-v2-ach__level {
  align-items: center;
}

.r-v2-ach__medal {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: var(--r-radius-full);
  border: 2px solid var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 16%, transparent);
}

.r-v2-ach__level-value,
.r-v2-ach__stat-value,
.r-v2-ach__pct,
.r-v2-ach__total-value {
  font-variant-numeric: tabular-nums;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  line-height: 1;
}

.r-v2-ach__level-value {
  font-size: var(--r-font-size-3xl);
  letter-spacing: -0.03em;
}

.r-v2-ach__progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-v2-ach__track {
  display: block;
  width: 112px;
  height: 4px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-border-strong);
  overflow: hidden;
}

.r-v2-ach__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--r-color-brand-primary);
}

.r-v2-ach__progress-pct {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
  font-variant-numeric: tabular-nums;
}

.r-v2-ach__total {
  align-items: flex-end;
}

.r-v2-ach__total-value {
  font-size: var(--r-font-size-xl);
}

.r-v2-ach__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  color: var(--r-color-fg);
}

.r-v2-ach__count--zero {
  color: var(--r-color-fg-faint);
}

.r-v2-ach__count--progression:not(.r-v2-ach__count--zero) :deep(.r-icon) {
  color: var(--r-color-brand-primary);
}
.r-v2-ach__count--missable:not(.r-v2-ach__count--zero) :deep(.r-icon) {
  color: var(--r-color-warning);
}
.r-v2-ach__count--win_condition:not(.r-v2-ach__count--zero) :deep(.r-icon) {
  color: var(--r-color-success);
}
.r-v2-ach__count--other:not(.r-v2-ach__count--zero) :deep(.r-icon) {
  color: var(--r-color-fg-muted);
}

.r-v2-ach__games,
.r-v2-ach__grid {
  list-style: none;
  margin: 0;
  padding: 0;
}

.r-v2-ach__row {
  appearance: none;
  width: 100%;
  min-height: 76px;
  padding: 10px 0;
  border: 0;
  border-bottom: 1px solid var(--r-color-border);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-ach__row:hover {
  background: var(--r-color-bg-elevated);
}

.r-v2-ach__row:focus-visible {
  outline: 2px solid var(--r-color-brand-primary);
  outline-offset: -2px;
}

.r-v2-ach__game {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.r-v2-ach__platform-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.r-v2-ach__cover {
  position: relative;
  width: 56px;
  height: 56px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
}

.r-v2-ach__cover :deep(.r-image),
.r-v2-ach__icon :deep(.r-image),
.r-v2-ach__art :deep(.r-image) {
  position: absolute;
  inset: 0;
}

.r-v2-ach__cover :deep(.r-image__layer > .r-skeleton),
.r-v2-ach__icon :deep(.r-image__layer > .r-skeleton),
.r-v2-ach__art :deep(.r-image__layer > .r-skeleton) {
  position: absolute;
  inset: 0;
}

.r-v2-ach__game-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}

.r-v2-ach__game-name {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-heading);
}

.r-v2-ach__pct {
  justify-self: end;
  font-size: var(--r-font-size-2xl);
  letter-spacing: -0.03em;
}

.r-v2-ach__toolbar {
  display: flex;
  width: 100%;
  padding: var(--r-space-2) 0 var(--r-space-4);
}

.r-v2-ach__sort {
  width: min(320px, 100%);
}

.r-v2-ach__detail-head {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-5);
  padding-bottom: var(--r-space-2);
}

.r-v2-ach__detail-top {
  display: flex;
  align-items: center;
  gap: var(--r-space-4);
  min-width: 0;
}

.r-v2-ach__icon {
  position: relative;
  width: 72px;
  height: 72px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  box-shadow: 0 0 0 1px var(--r-color-border);
}

.r-v2-ach__detail-name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.r-v2-ach__detail-name h1 {
  margin: 0;
  font-size: var(--r-font-size-2xl);
  font-weight: var(--r-font-weight-extrabold);
  letter-spacing: -0.03em;
  line-height: var(--r-line-height-tight);
  color: var(--r-color-fg-heading);
}

.r-v2-ach__detail-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--r-space-6) var(--r-space-8);
}

.r-v2-ach__stat-value {
  font-size: var(--r-font-size-3xl);
  letter-spacing: -0.03em;
}

.r-v2-ach__counts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-4);
  margin-left: auto;
}

.r-v2-ach__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
  gap: 12px;
}

.r-v2-ach__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 6px;
  min-height: 248px;
  padding: 18px 14px 16px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
}

.r-v2-ach__card--locked .r-v2-ach__card-title,
.r-v2-ach__card--locked .r-v2-ach__card-desc,
.r-v2-ach__card--locked .r-v2-ach__type {
  opacity: 0.55;
}

.r-v2-ach__art {
  position: relative;
  width: 104px;
  height: 104px;
  display: grid;
  place-items: center;
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  background: var(--r-color-surface);
}

.r-v2-ach__art--fallback {
  border-radius: var(--r-radius-full);
  background: color-mix(in srgb, var(--r-color-brand-primary) 16%, transparent);
}

.r-v2-ach__card--locked .r-v2-ach__art :deep(.r-image--loaded .r-image__image) {
  filter: grayscale(1);
  opacity: 0.7;
}

.r-v2-ach__lock {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--r-color-bg) 42%, transparent);
  color: var(--r-color-fg);
}

.r-v2-ach__type {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.r-v2-ach__card-title {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.r-v2-ach__card-desc {
  margin: 0;
  font-size: var(--r-font-size-sm);
  line-height: var(--r-line-height-normal);
  color: var(--r-color-fg-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.r-v2-ach__skeletons {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

@media (max-width: 860px) {
  .r-v2-ach__head,
  .r-v2-ach__row {
    grid-template-columns: minmax(0, 1fr) 58px repeat(4, 40px);
    column-gap: 8px;
  }

  .r-v2-ach__pct,
  .r-v2-ach__total-value,
  .r-v2-ach__level-value {
    font-size: var(--r-font-size-xl);
  }

  .r-v2-ach__counts {
    margin-left: 0;
  }

  .r-v2-ach__icon {
    width: 56px;
    height: 56px;
  }
}

/* Phones: the desktop columns don't fit. Title and game name take a full
   line; counts wrap underneath. Desktop (600px and up) stays a single row. */
html[data-bp~="xs"] .r-v2-ach__head,
html[data-bp~="xs"] .r-v2-ach__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: 12px;
  row-gap: 8px;
  max-width: 100%;
  min-width: 0;
}

html[data-bp~="xs"] .r-v2-ach__page-title,
html[data-bp~="xs"] .r-v2-ach__game {
  flex: 1 0 100%;
  min-width: 0;
}

html[data-bp~="xs"] .r-v2-ach__game-name {
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  text-overflow: unset;
}

html[data-bp~="xs"] .r-v2-ach__detail-head {
  max-width: 100%;
  min-width: 0;
}

html[data-bp~="xs"] .r-v2-ach__detail-top {
  align-items: flex-start;
}

html[data-bp~="xs"] .r-v2-ach__detail-name h1 {
  white-space: normal;
}
</style>
