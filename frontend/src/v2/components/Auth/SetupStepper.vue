<script setup lang="ts">
// SetupStepper — presentational step indicator: a horizontal row of
// numbered dots connected by lines. Past dots are filled, the current
// dot is the brand-tinted active state, future dots are muted outlines.
import { RIcon } from "@v2/lib";
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  current: number;
  total: number;
}

const props = defineProps<Props>();

const items = computed(() =>
  Array.from({ length: props.total }, (_, i) => {
    const index = i + 1;
    let state: "past" | "current" | "future";
    if (index < props.current) state = "past";
    else if (index === props.current) state = "current";
    else state = "future";
    return { index, state };
  }),
);
</script>

<template>
  <ol class="r-setup-stepper" :aria-label="`Step ${current} of ${total}`">
    <template v-for="(item, i) in items" :key="item.index">
      <li class="r-setup-stepper__dot" :data-state="item.state">
        <RIcon v-if="item.state === 'past'" name="mdi-check" :size="16" />
        <span v-else>{{ item.index }}</span>
      </li>
      <li
        v-if="i < items.length - 1"
        class="r-setup-stepper__line"
        :data-active="items[i + 1]?.state !== 'future'"
        aria-hidden="true"
      />
    </template>
  </ol>
</template>

<style scoped>
.r-setup-stepper {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  list-style: none;
  margin: 0;
  padding: 0;
  justify-self: center;
}

.r-setup-stepper__dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  transition:
    background 200ms ease,
    color 200ms ease,
    border-color 200ms ease,
    box-shadow 200ms ease;
}

.r-setup-stepper__dot[data-state="past"] {
  background: var(--r-color-brand-primary);
  color: white;
  border-color: var(--r-color-brand-primary);
}

.r-setup-stepper__dot[data-state="current"] {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 0 0 4px
    color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}

.r-setup-stepper__line {
  width: 56px;
  height: 2px;
  background: var(--r-color-border);
  border-radius: var(--r-radius-pill);
  transition: background 200ms ease;
}

.r-setup-stepper__line[data-active="true"] {
  background: var(--r-color-brand-primary);
}

@media (max-width: 600px) {
  .r-setup-stepper__line {
    width: 32px;
  }
}
</style>
