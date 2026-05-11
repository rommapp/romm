<script setup lang="ts">
// RMenuSearch — small search/filter input designed to sit at the
// top of an RMenuPanel. Visually identical to v2's prefix-label
// fields: a compact icon-only well on the left, a divider, and the
// query input on the right.
//
// Two ways to use it:
//
//   1. Recommended — let RMenuPanel render it for you via the
//      `searchable` prop. The panel takes care of layout so the
//      items below don't scroll behind the header.
//
//   2. Manually — drop it as the first child of an RMenuPanel
//      when you need custom placement. Set
//      `:close-on-content-click="false"` on the wrapping RMenu so
//      typing doesn't dismiss it; close the menu explicitly from
//      item handlers.
import { onMounted, ref } from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RTextField from "../../forms/RTextField/RTextField.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: string;
  placeholder?: string;
  /** Auto-focus the input on mount so the menu opens ready to type. */
  autoFocus?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: "",
  placeholder: "",
  autoFocus: true,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const inputRef = ref<{ $el?: HTMLElement } | null>(null);

onMounted(() => {
  if (!props.autoFocus) return;
  // The menu fades in over a tick; defer focus to the next frame so
  // the browser actually moves focus instead of bouncing it back.
  requestAnimationFrame(() => {
    const el = inputRef.value?.$el?.querySelector("input");
    el?.focus();
  });
});
</script>

<template>
  <div class="r-menu-search" @click.stop @mousedown.stop>
    <RTextField
      ref="inputRef"
      :model-value="modelValue"
      :placeholder="placeholder"
      prefix-label
      hide-details
      density="compact"
      autocomplete="off"
      class="r-menu-search__field"
      @update:model-value="(v) => emit('update:modelValue', String(v ?? ''))"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="16" />
      </template>
    </RTextField>
  </div>
</template>

<style scoped>
/* `position: sticky` is a no-op when the parent doesn't scroll
   (e.g. RMenuPanel's `header` zone, which sits outside the body's
   overflow). Inside contexts that DO scroll — VSelect's
   `#prepend-item` inside a v-list — sticky kicks in and keeps the
   search visible at the top. Opaque background occludes items
   scrolling underneath. */
.r-menu-search {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  background: var(--r-color-surface);
}
.r-menu-search__field {
  flex: 1;
}
</style>
