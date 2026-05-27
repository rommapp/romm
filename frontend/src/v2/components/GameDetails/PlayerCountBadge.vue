<script setup lang="ts">
// PlayerCountBadge — renders `metadatum.player_count` as a single
// semantic badge. The icon swaps with the maximum number of players
// the string mentions:
//   1            → mdi-account-outline       ("Single player")
//   2            → mdi-account-multiple-outline
//   3–4          → mdi-account-group-outline
//   5+           → mdi-account-multiple-plus-outline
// The string the API returns is free-form (the providers feed it as
// a bare number, a range, or a sentence — "1", "1-4", "Up to 4
// players", "Single Player", "Massively Multiplayer" …). We pull
// the largest integer out as the signal and fall back to a generic
// group icon when no digit is parseable, so non-numeric descriptors
// still render with an appropriate "more than one person" affordance.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ value: string }>();

const { t } = useI18n();

const maxPlayers = computed<number | null>(() => {
  const matches = props.value.match(/\d+/g);
  if (!matches) return null;
  return Math.max(...matches.map(Number));
});

const icon = computed(() => {
  const n = maxPlayers.value;
  if (n === null) return "mdi-account-group-outline";
  if (n <= 1) return "mdi-account-outline";
  if (n === 2) return "mdi-account-multiple-outline";
  if (n <= 4) return "mdi-account-group-outline";
  return "mdi-account-multiple-plus-outline";
});

const label = computed(() => {
  const n = maxPlayers.value;
  if (n === 1) return t("rom.single-player");
  if (n !== null && n > 1) return t("rom.players-n", { n: props.value });
  return props.value;
});
</script>

<template>
  <div class="player-count">
    <RIcon :icon="icon" size="16" class="player-count__icon" />
    <span class="player-count__label">{{ label }}</span>
  </div>
</template>

<style scoped>
.player-count {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 10px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-pill);
  font-size: 12px;
  color: var(--r-color-fg-secondary);
}
.player-count__icon {
  color: var(--r-color-brand-primary);
}
.player-count__label {
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.01em;
}
</style>
