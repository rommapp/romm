<script setup lang="ts">
import { RAvatar, RSwitch, RTooltip } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type {
  HashMatcher,
  HashMatcherKey,
} from "@/v2/composables/useScanProviders";

defineProps<{
  matchers: HashMatcher[];
  isOn: (matcher: HashMatcher) => boolean;
}>();
const emit = defineEmits<{
  toggle: [value: HashMatcherKey, next: boolean];
}>();

const { t } = useI18n();

function tipText(matcher: HashMatcher): string {
  return matcher.blockedReason
    ? `${matcher.name}: ${matcher.blockedReason}`
    : matcher.name;
}
</script>

<template>
  <div
    class="r-v2-hash-matchers"
    role="group"
    :aria-label="t('scan.hash-matchers')"
  >
    <RTooltip
      v-for="matcher in matchers"
      :key="matcher.value"
      :text="tipText(matcher)"
      location="bottom"
      :open-on-tap="!matcher.switchEnabled"
    >
      <template #activator="{ props: tipProps }">
        <div
          v-bind="tipProps"
          :tabindex="matcher.switchEnabled ? undefined : 0"
          :role="matcher.switchEnabled ? undefined : 'group'"
          :aria-label="matcher.switchEnabled ? undefined : tipText(matcher)"
          class="r-v2-hash-matchers__matcher"
          :class="{
            'r-v2-hash-matchers__matcher--off': !matcher.switchEnabled,
          }"
        >
          <RAvatar
            :image="matcher.logo"
            size="16"
            rounded="sm"
            class="r-v2-hash-matchers__logo"
          />
          <RSwitch
            :model-value="isOn(matcher)"
            :disabled="!matcher.switchEnabled"
            :aria-label="matcher.name"
            class="r-v2-hash-matchers__switch"
            @update:model-value="(v) => emit('toggle', matcher.value, v)"
          />
        </div>
      </template>
    </RTooltip>
  </div>
</template>

<style scoped>
.r-v2-hash-matchers {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  align-self: flex-start;
}
.r-v2-hash-matchers__matcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}
.r-v2-hash-matchers__matcher--off {
  opacity: 0.55;
}
/* A disabled button swallows taps, so let them reach the pill's tooltip. */
.r-v2-hash-matchers__matcher--off .r-v2-hash-matchers__switch {
  pointer-events: none;
}
.r-v2-hash-matchers__logo {
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
}
</style>
