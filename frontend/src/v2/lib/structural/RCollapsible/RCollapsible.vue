<script setup lang="ts">
// RCollapsible — animated disclosure panel. Two modes:
//
//   * Self-contained — pass `title` (and optionally `icon`) or use the
//     `#header` slot. The header acts as the trigger and renders the
//     chevron. Best for cards like "Related games" where the panel
//     owns its own toggle row. The `#header-prepend` slot drops content
//     before the title (custom avatars/images that can't fit the MDI
//     `icon` prop); `#header-append` drops content between the title
//     and the chevron (counters, badges, status chips).
//
//   * Headless — no `title`/`icon`/`#header` provided. The internal
//     header is skipped entirely; the panel is a pure animated body
//     driven by `modelValue` from the outside. Best when the trigger
//     lives in the parent (e.g., a sidebar tab that opens an attached
//     actions panel below it).
//
// `attached` removes the top radius and top border so the panel sits
// flush with a trigger element placed directly above it (the trigger
// is responsible for dropping its own bottom radius).
//
// Animation uses a CSS-only grid-row trick (no JS height measurement)
// so it works for content of any height.
import { computed, ref, useSlots, watch } from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: boolean;
  defaultOpen?: boolean;
  title?: string;
  icon?: string;
  disabled?: boolean;
  attached?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  defaultOpen: false,
  title: undefined,
  icon: undefined,
  disabled: false,
  attached: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
}>();

const slots = useSlots();

// Uncontrolled mode: keep our own ref. Controlled mode: prop is the
// source of truth, we never write the local ref.
const isControlled = computed(() => props.modelValue !== undefined);
const localOpen = ref(props.defaultOpen);
const open = computed(() =>
  isControlled.value ? Boolean(props.modelValue) : localOpen.value,
);

watch(
  () => props.modelValue,
  (v) => {
    if (v !== undefined) localOpen.value = v;
  },
);

// Headless only when no header-shaped content is present — title prop
// or slot, icon, full #header override, or any header-prepend /
// header-append slot all count as "the consumer wants a header row".
// (Previously we only checked `slots.header` + `props.title` + props.icon,
// which silently hid the trigger when a caller used `#title` /
// `#header-prepend` without also passing the `title` prop.)
const hasHeader = computed(
  () =>
    Boolean(slots.header) ||
    Boolean(slots.title) ||
    Boolean(slots["header-prepend"]) ||
    Boolean(slots["header-append"]) ||
    Boolean(props.title) ||
    Boolean(props.icon),
);

function toggle() {
  if (props.disabled) return;
  const next = !open.value;
  if (!isControlled.value) localOpen.value = next;
  emit("update:modelValue", next);
}
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-collapsible"
    :class="{
      'r-collapsible--open': open,
      'r-collapsible--disabled': disabled,
      'r-collapsible--attached': attached,
      'r-collapsible--headless': !hasHeader,
    }"
  >
    <button
      v-if="hasHeader"
      type="button"
      class="r-collapsible__header"
      :aria-expanded="open"
      :disabled="disabled"
      @click="toggle"
    >
      <slot name="header">
        <span
          v-if="slots['header-prepend']"
          class="r-collapsible__header-prepend"
        >
          <slot name="header-prepend" />
        </span>
        <RIcon v-if="icon" :icon="icon" class="r-collapsible__icon" />
        <span class="r-collapsible__title">
          <slot name="title">{{ title }}</slot>
        </span>
        <span
          v-if="slots['header-append']"
          class="r-collapsible__header-append"
        >
          <slot name="header-append" />
        </span>
        <RIcon
          icon="mdi-chevron-down"
          class="r-collapsible__chevron r-chevron-toggle"
        />
      </slot>
    </button>

    <div class="r-collapsible__content-wrap" :aria-hidden="!open">
      <div class="r-collapsible__content">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-collapsible {
  /* Default: surface always visible. The header IS the trigger in
     self-contained mode, so it must read as a clickable surface even
     when the body is collapsed. */
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  transition:
    background var(--r-motion-med) var(--r-motion-ease-out),
    border-color var(--r-motion-med) var(--r-motion-ease-out);
}
/* Headless mode has an external trigger — the panel itself shouldn't
   paint anything when closed (otherwise a stray 1px line lives under
   every inactive sidebar tab). Surface fades in alongside the height
   when the consumer opens it. */
.r-collapsible--headless:not(.r-collapsible--open) {
  background: transparent;
  border-color: transparent;
}
.r-collapsible--disabled {
  opacity: 0.5;
}
.r-collapsible--attached {
  border-top-width: 0;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

.r-collapsible__header {
  appearance: none;
  border: 0;
  background: transparent;
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-4) var(--r-space-5);
  font-family: inherit;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-collapsible__header:hover:not(:disabled) {
  background: var(--r-color-surface-hover);
}
.r-collapsible__header:disabled {
  cursor: not-allowed;
}

.r-collapsible__icon {
  color: var(--r-color-fg-muted);
}

.r-collapsible__title {
  flex: 1;
  text-align: left;
}

.r-collapsible__header-prepend,
.r-collapsible__header-append {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.r-collapsible__chevron {
  color: var(--r-color-fg-muted);
}

/* Smooth open via grid-row trick — content height interpolates without
   a measured pixel value, so it works for any content.
   Wrap stays overflow:hidden in both states so partial-frame content
   never bleeds during the transition. */
.r-collapsible__content-wrap {
  display: grid;
  grid-template-rows: 0fr;
  overflow: hidden;
  transition: grid-template-rows var(--r-motion-med) var(--r-motion-ease-out);
}
.r-collapsible--open .r-collapsible__content-wrap {
  grid-template-rows: 1fr;
}
.r-collapsible__content {
  min-height: 0;
}

/* Default content padding only when there's a header — applied to the
   first child (not to .content itself) so the grid item can collapse
   to 0px when closed. Padding on the item would force min-content >= 0,
   leaking the first line of content under the header.
   In headless mode the consumer drives padding so the panel can blend
   with custom triggers. */
.r-collapsible:not(.r-collapsible--headless)
  .r-collapsible__content
  > :first-child {
  padding: 0 var(--r-space-5) var(--r-space-5);
}
</style>
