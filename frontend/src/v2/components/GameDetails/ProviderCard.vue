<script setup lang="ts">
// ProviderCard — single metadata-source card. Provider name + logo
// + linked external ID (or "Not linked"). When `url` is non-null and
// the ID is set, the card renders as an `<a target=_blank>`; otherwise
// it's a static div. Brand colour is consumed via the `accent` prop
// (caller passes a CSS color value, typically a token reference).
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

interface Props {
  name: string;
  accent: string;
  logo?: string | null;
  id?: string | number | null;
  href?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  logo: null,
  id: null,
  href: null,
});

const isLinked = computed(() => props.id !== null && props.id !== undefined);
const isClickable = computed(() => isLinked.value && Boolean(props.href));
</script>

<template>
  <component
    :is="isClickable ? 'a' : 'div'"
    class="provider-card"
    :class="{ 'provider-card--unlinked': !isLinked }"
    :style="{ '--provider-accent': accent }"
    :href="isClickable ? href : undefined"
    :target="isClickable ? '_blank' : undefined"
    :rel="isClickable ? 'noopener' : undefined"
  >
    <div class="provider-card__head">
      <img
        v-if="logo"
        :src="logo"
        :alt="name"
        class="provider-card__logo"
        loading="lazy"
        @error="($event.target as HTMLImageElement).style.display = 'none'"
      />
      <span class="provider-card__name">{{ name }}</span>
      <RIcon
        v-if="isClickable"
        icon="mdi-open-in-new"
        size="14"
        class="provider-card__open"
      />
    </div>
    <div class="provider-card__id">
      <span v-if="isLinked">{{ id }}</span>
      <span v-else class="provider-card__unlinked">
        {{ t("common.not-linked") }}
      </span>
    </div>
  </component>
</template>

<style scoped>
.provider-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  text-decoration: none;
  color: var(--r-color-fg);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.provider-card[href]:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--provider-accent);
  transform: translateY(-1px);
}
.provider-card--unlinked {
  opacity: 0.55;
}

.provider-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.provider-card__logo {
  width: 16px;
  height: 16px;
  object-fit: contain;
  border-radius: 2px;
}
.provider-card__name {
  flex: 1;
  font-size: 12.5px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.provider-card__open {
  color: var(--r-color-fg-muted);
}

.provider-card__id {
  font-size: 11.5px;
  color: var(--r-color-fg-secondary);
  font-variant-numeric: tabular-nums;
  font-family: var(--r-font-family-mono);
}
.provider-card__unlinked {
  font-style: italic;
  color: var(--r-color-fg-faint);
  font-family: var(--r-font-family-sans);
}
</style>
