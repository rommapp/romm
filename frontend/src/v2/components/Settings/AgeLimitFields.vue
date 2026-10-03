<script setup lang="ts">
// AgeLimitFields: a group's or user's age limit and unrated-games rule.
// A user's null keeps the group's value, which `inherited` describes.
import { RIcon, RSelect, RSwitch } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  inherited?: { ageLimit: number | null; hideUnrated: boolean };
}>();

const ageLimit = defineModel<number | null>("ageLimit", { required: true });
const hideUnrated = defineModel<boolean | null>("hideUnrated", {
  required: true,
});

const { t } = useI18n();

// The thresholds the common rating boards use.
const AGE_OPTIONS = [3, 6, 7, 10, 12, 13, 15, 16, 17, 18];

function ageText(age: number | null): string {
  return age === null
    ? t("settings.age-limit-none")
    : t("settings.age-limit-option", { age });
}

// RSelect shows nothing for a value outside its items, so a limit the API set
// to another age joins the list.
const ages = computed(() => {
  const current = ageLimit.value;
  return current === null || AGE_OPTIONS.includes(current)
    ? AGE_OPTIONS
    : [...AGE_OPTIONS, current].sort((a, b) => a - b);
});

const ageItems = computed(() => [
  {
    title: props.inherited
      ? t("settings.age-limit-inherit", {
          setting: ageText(props.inherited.ageLimit),
        })
      : ageText(null),
    value: null,
  },
  ...ages.value.map((age) => ({ title: ageText(age), value: age })),
]);

function unratedText(hide: boolean): string {
  return hide
    ? t("settings.hide-unrated-games")
    : t("settings.show-unrated-games");
}

const unratedItems = computed(() => [
  {
    title: t("settings.age-limit-inherit", {
      setting: unratedText(props.inherited?.hideUnrated ?? false),
    }),
    value: null,
  },
  { title: unratedText(false), value: false },
  { title: unratedText(true), value: true },
]);
</script>

<template>
  <div v-bind="$attrs" class="r-v2-age-limit">
    <RSelect
      v-model="ageLimit"
      variant="outlined"
      :items="ageItems"
      item-title="title"
      item-value="value"
      prefix-label="stacked"
      :hint="t('settings.age-limit-hint')"
    >
      <template #prefix-label>
        <RIcon icon="mdi-account-child-outline" size="14" />
        {{ t("settings.age-limit") }}
      </template>
    </RSelect>

    <RSelect
      v-if="inherited"
      v-model="hideUnrated"
      variant="outlined"
      :items="unratedItems"
      item-title="title"
      item-value="value"
      prefix-label="stacked"
      :hint="t('settings.unrated-games-hint')"
    >
      <template #prefix-label>
        <RIcon icon="mdi-help-rhombus-outline" size="14" />
        {{ t("settings.unrated-games") }}
      </template>
    </RSelect>
    <div v-else class="r-v2-age-limit__switch">
      <RSwitch
        :model-value="hideUnrated ?? false"
        :label="t('settings.hide-unrated-games')"
        @update:model-value="hideUnrated = $event"
      />
      <span class="r-v2-age-limit__switch-hint">
        {{ t("settings.unrated-games-hint") }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.r-v2-age-limit {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.r-v2-age-limit__switch {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.r-v2-age-limit__switch-hint {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
