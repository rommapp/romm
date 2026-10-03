<script setup lang="ts">
// AgeLimitFields: a group's or user's age limit, unrated rule and allowed games.
// A user's null keeps the group's value, which `inherited` describes.
import { RSelect, RSwitch } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import HiddenGamesPicker from "./HiddenGamesPicker.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  inherited?: { ageLimit: number | null; hideUnrated: boolean };
}>();

const ageLimit = defineModel<number | null>("ageLimit", { required: true });
const hideUnrated = defineModel<boolean | null>("hideUnrated", {
  required: true,
});
const exemptRomIds = defineModel<number[]>("exemptRomIds", { required: true });

const { t } = useI18n();

// The thresholds the common rating boards use.
const AGE_OPTIONS = [3, 6, 7, 10, 12, 13, 15, 16, 17, 18];

// RSelect reads a null model as "nothing selected", so null gets a key.
const UNSET = "unset";
type AgeChoice = number | typeof UNSET;
type UnratedChoice = "show" | "hide" | typeof UNSET;

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
    value: UNSET,
  },
  ...ages.value.map((age) => ({ title: ageText(age), value: age })),
]);

const ageChoice = computed<AgeChoice>({
  get: () => ageLimit.value ?? UNSET,
  set: (choice) => {
    ageLimit.value = choice === UNSET ? null : choice;
  },
});

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
    value: UNSET,
  },
  { title: unratedText(false), value: "show" },
  { title: unratedText(true), value: "hide" },
]);

const unratedChoice = computed<UnratedChoice>({
  get: () =>
    hideUnrated.value === null ? UNSET : hideUnrated.value ? "hide" : "show",
  set: (choice) => {
    hideUnrated.value = choice === UNSET ? null : choice === "hide";
  },
});
</script>

<template>
  <div v-bind="$attrs" class="r-v2-age-limit">
    <div class="r-v2-age-limit__field">
      <span class="r-v2-age-limit__label">
        {{ t("settings.age-limit") }}
      </span>
      <span class="r-v2-age-limit__hint">
        {{ t("settings.age-limit-hint") }}
      </span>
      <RSelect
        v-model="ageChoice"
        variant="outlined"
        :items="ageItems"
        item-title="title"
        item-value="value"
        :label="t('settings.age-limit')"
        hide-details
      />
    </div>

    <div v-if="inherited" class="r-v2-age-limit__field">
      <span class="r-v2-age-limit__label">
        {{ t("settings.unrated-games") }}
      </span>
      <span class="r-v2-age-limit__hint">
        {{ t("settings.unrated-games-hint") }}
      </span>
      <RSelect
        v-model="unratedChoice"
        variant="outlined"
        :items="unratedItems"
        item-title="title"
        item-value="value"
        :label="t('settings.unrated-games')"
        hide-details
      />
    </div>
    <div v-else class="r-v2-age-limit__switch">
      <RSwitch
        :model-value="hideUnrated ?? false"
        :label="t('settings.hide-unrated-games')"
        @update:model-value="hideUnrated = $event"
      />
      <span class="r-v2-age-limit__hint">
        {{ t("settings.unrated-games-hint") }}
      </span>
    </div>

    <div class="r-v2-age-limit__field">
      <span class="r-v2-age-limit__label">
        {{ t("settings.age-exemptions") }}
      </span>
      <span class="r-v2-age-limit__hint">
        {{ t("settings.age-exemptions-hint") }}
      </span>
      <HiddenGamesPicker
        v-model="exemptRomIds"
        :placeholder="t('settings.age-exemptions-search')"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-age-limit {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.r-v2-age-limit__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.r-v2-age-limit__switch {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.r-v2-age-limit__label {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}
.r-v2-age-limit__hint {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
