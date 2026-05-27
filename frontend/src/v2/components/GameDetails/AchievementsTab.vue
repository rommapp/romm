<script setup lang="ts">
// AchievementsTab — RetroAchievements summary + filter row + per-achievement
// list. The "earned" set comes from the parent (computed off
// auth.user.ra_progression so it stays reactive); rows look up by
// `badge_id` against the set in O(1).
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { RAGameRomAchievement, RomRAMetadata } from "@/__generated__";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const props = withDefaults(
  defineProps<{
    metadata: RomRAMetadata | null | undefined;
    apiBase?: string;
    earnedAchievementIds?: ReadonlySet<string>;
  }>(),
  {
    apiBase: undefined,
    earnedAchievementIds: () => new Set<string>(),
  },
);

type TypeFilter = "all" | "progression" | "missable" | "win_condition";
type StatusFilter = "all" | "earned" | "locked";

const typeFilter = ref<TypeFilter>("all");
const statusFilter = ref<StatusFilter>("all");

const achievements = computed<RAGameRomAchievement[]>(
  () => props.metadata?.achievements ?? [],
);

const totalPoints = computed(() =>
  achievements.value.reduce((sum, a) => sum + (a.points ?? 0), 0),
);
const progressionCount = computed(
  () => achievements.value.filter((a) => a.type === "progression").length,
);
const missableCount = computed(
  () => achievements.value.filter((a) => a.type === "missable").length,
);

function isEarned(a: RAGameRomAchievement) {
  return Boolean(a.badge_id && props.earnedAchievementIds.has(a.badge_id));
}
const earnedCount = computed(() => achievements.value.filter(isEarned).length);

const filtered = computed<RAGameRomAchievement[]>(() => {
  let list = achievements.value;
  if (typeFilter.value !== "all") {
    list = list.filter((a) => a.type === typeFilter.value);
  }
  if (statusFilter.value === "earned") {
    list = list.filter(isEarned);
  } else if (statusFilter.value === "locked") {
    list = list.filter((a) => !isEarned(a));
  }
  return list;
});

function badgeSrc(a: RAGameRomAchievement) {
  const path = isEarned(a) ? a.badge_path : a.badge_path_lock;
  if (path && props.apiBase) return `${props.apiBase}${path}`;
  return (isEarned(a) ? a.badge_url : a.badge_url_lock) ?? "";
}

function toggleStatus(target: StatusFilter) {
  statusFilter.value = statusFilter.value === target ? "all" : target;
}

function typeFilterLabel(f: TypeFilter): string {
  switch (f) {
    case "all":
      return t("rom.achievements-filter-all");
    case "progression":
      return t("rom.achievements-filter-progression");
    case "missable":
      return t("rom.achievements-filter-missable");
    case "win_condition":
      return t("rom.achievements-filter-win-condition");
  }
}

function achievementTypeLabel(type: string | null | undefined): string {
  switch (type) {
    case "progression":
      return t("rom.achievements-type-progression");
    case "missable":
      return t("rom.achievements-type-missable");
    case "win_condition":
      return t("rom.achievements-type-win-condition");
    default:
      return type ?? "";
  }
}
</script>

<template>
  <section class="r-v2-det-ach">
    <div v-if="!achievements.length" class="r-v2-det-ach__empty">
      {{ t("rom.achievements-no-data") }}
    </div>

    <template v-else>
      <header class="r-v2-det-ach__summary">
        <div class="r-v2-det-ach__stat">
          <div class="r-v2-det-ach__stat-val">
            {{ earnedCount }} / {{ achievements.length }}
          </div>
          <div class="r-v2-det-ach__stat-lbl">{{ t("rom.achievements") }}</div>
        </div>
        <div class="r-v2-det-ach__stat">
          <div class="r-v2-det-ach__stat-val">
            {{ totalPoints }}
          </div>
          <div class="r-v2-det-ach__stat-lbl">
            {{ t("rom.achievements-total-points") }}
          </div>
        </div>
        <div v-if="progressionCount" class="r-v2-det-ach__stat">
          <div class="r-v2-det-ach__stat-val">
            {{ progressionCount }}
          </div>
          <div class="r-v2-det-ach__stat-lbl">
            {{ t("rom.achievements-progression") }}
          </div>
        </div>
        <div v-if="missableCount" class="r-v2-det-ach__stat">
          <div class="r-v2-det-ach__stat-val r-v2-det-ach__stat-val--missable">
            {{ missableCount }}
          </div>
          <div class="r-v2-det-ach__stat-lbl">
            {{ t("rom.achievements-missable") }}
          </div>
        </div>
      </header>

      <div class="r-v2-det-ach__filters">
        <button
          v-for="f in [
            'all',
            'progression',
            'missable',
            'win_condition',
          ] as TypeFilter[]"
          :key="f"
          type="button"
          class="r-v2-det-ach__filter"
          :class="{ 'r-v2-det-ach__filter--active': typeFilter === f }"
          @click="typeFilter = f"
        >
          {{ typeFilterLabel(f) }}
        </button>
        <span class="r-v2-det-ach__filter-sep" />
        <button
          type="button"
          class="r-v2-det-ach__filter r-v2-det-ach__filter--earned"
          :class="{ 'r-v2-det-ach__filter--active': statusFilter === 'earned' }"
          @click="toggleStatus('earned')"
        >
          ✓ {{ t("rom.achievements-earned") }}
        </button>
        <button
          type="button"
          class="r-v2-det-ach__filter r-v2-det-ach__filter--locked"
          :class="{ 'r-v2-det-ach__filter--active': statusFilter === 'locked' }"
          @click="toggleStatus('locked')"
        >
          ⊘ {{ t("rom.achievements-locked") }}
        </button>
      </div>

      <div class="r-v2-det-ach__grid">
        <article
          v-for="a in filtered"
          :key="a.ra_id ?? a.title ?? undefined"
          class="r-v2-det-ach__row"
          :class="{ 'r-v2-det-ach__row--locked': !isEarned(a) }"
        >
          <div class="r-v2-det-ach__badge">
            <img
              v-if="badgeSrc(a)"
              :src="badgeSrc(a)"
              :alt="a.title ?? ''"
              loading="lazy"
              @error="
                ($event.target as HTMLImageElement).style.visibility = 'hidden'
              "
            />
          </div>
          <div class="r-v2-det-ach__text">
            <div class="r-v2-det-ach__title">
              {{ a.title }}
            </div>
            <div class="r-v2-det-ach__desc">
              {{ a.description }}
            </div>
          </div>
          <div class="r-v2-det-ach__right">
            <div class="r-v2-det-ach__points">
              {{ t("rom.achievements-points-n", { n: a.points ?? 0 }) }}
            </div>
            <span
              v-if="a.type"
              class="r-v2-det-ach__type"
              :class="`r-v2-det-ach__type--${a.type}`"
            >
              {{ achievementTypeLabel(a.type) }}
            </span>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.r-v2-det-ach {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-det-ach__empty {
  padding: 30px 0;
  color: var(--r-color-fg-faint);
  font-size: 13px;
  font-style: italic;
  text-align: center;
}

/* ── Summary ─────────────────────────────────────────── */
.r-v2-det-ach__summary {
  display: flex;
  gap: 0;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  padding: 14px 0;
}
.r-v2-det-ach__stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  border-right: 1px solid var(--r-color-border);
  padding: 0 12px;
}
.r-v2-det-ach__stat:last-child {
  border-right: none;
}
.r-v2-det-ach__stat-val {
  font-size: 20px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  font-variant-numeric: tabular-nums;
}
.r-v2-det-ach__stat-val--missable {
  color: var(--r-color-warning);
}
.r-v2-det-ach__stat-lbl {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}

/* ── Filters ─────────────────────────────────────────── */
.r-v2-det-ach__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.r-v2-det-ach__filter {
  appearance: none;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  color: var(--r-color-fg-secondary);
  padding: 5px 13px;
  font-size: 11.5px;
  font-weight: var(--r-font-weight-medium);
  cursor: pointer;
  font-family: inherit;
  text-transform: capitalize;
  transition:
    background var(--r-motion-fast),
    color var(--r-motion-fast),
    border-color var(--r-motion-fast);
}
.r-v2-det-ach__filter:hover {
  color: var(--r-color-fg);
  background: var(--r-color-surface-hover);
}
.r-v2-det-ach__filter--active {
  color: var(--r-color-bg);
  background: var(--r-color-fg);
  border-color: var(--r-color-fg);
}
.r-v2-det-ach__filter--earned.r-v2-det-ach__filter--active {
  color: var(--r-color-fg);
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 30%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 50%,
    transparent
  );
}
.r-v2-det-ach__filter--locked.r-v2-det-ach__filter--active {
  color: var(--r-color-fg);
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 24%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 45%,
    transparent
  );
}
.r-v2-det-ach__filter-sep {
  width: 1px;
  height: 16px;
  background: var(--r-color-surface-hover);
  margin: 0 4px;
}

/* ── List ────────────────────────────────────────────── */
.r-v2-det-ach__grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-v2-det-ach__row {
  display: grid;
  grid-template-columns: 52px 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 10px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-det-ach__row--locked {
  opacity: 0.55;
}

.r-v2-det-ach__badge {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
}
.r-v2-det-ach__badge img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.r-v2-det-ach__title {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-det-ach__desc {
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  margin-top: 2px;
  line-height: 1.4;
}

.r-v2-det-ach__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  white-space: nowrap;
}
.r-v2-det-ach__points {
  font-size: 12px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-secondary);
  font-variant-numeric: tabular-nums;
}
.r-v2-det-ach__type {
  font-size: 9.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 8px;
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
}
.r-v2-det-ach__type--progression {
  background: color-mix(in srgb, var(--r-color-provider-igdb) 18%, transparent);
  color: color-mix(in srgb, var(--r-color-provider-igdb) 95%, transparent);
}
.r-v2-det-ach__type--missable {
  background: color-mix(in srgb, var(--r-color-warning) 18%, transparent);
  color: color-mix(in srgb, var(--r-color-warning-fg) 95%, transparent);
}
.r-v2-det-ach__type--win_condition {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 18%,
    transparent
  );
  color: color-mix(in srgb, var(--r-color-success) 95%, transparent);
}
</style>
