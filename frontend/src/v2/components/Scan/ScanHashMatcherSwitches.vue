<script setup lang="ts">
// ScanHashMatcherSwitches: one switch pill per hash-matcher proxy. A blocked
// matcher stays visible but disabled, with the reason in its tooltip.
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
      :text="
        matcher.blockedReason
          ? `${matcher.name}: ${matcher.blockedReason}`
          : matcher.name
      "
      location="bottom"
    >
      <template #activator="{ props: tipProps }">
        <div
          v-bind="tipProps"
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
.r-v2-hash-matchers__logo {
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
}
</style>
