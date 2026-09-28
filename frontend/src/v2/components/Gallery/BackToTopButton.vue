<script setup lang="ts">
// BackToTopButton: floating control that returns a long gallery scroll to
// its top, shown once the viewer is more than a viewport down.
import { RBtn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import { FOCUSABLE_SELECTOR } from "@/v2/utils/spatialNav";

interface Props {
  scroller: HTMLElement | null;
  scrollTop: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "scroll-to-top"): void;
}>();

const { t } = useI18n();
const { enabled: reducedMotion } = useReducedMotion();

const visible = computed(
  () => !!props.scroller && props.scrollTop > props.scroller.clientHeight,
);

function scrollToTop(event: MouseEvent) {
  const el = props.scroller;
  if (!el) return;
  emit("scroll-to-top");
  const hadFocus =
    event.currentTarget instanceof HTMLElement &&
    event.currentTarget.contains(document.activeElement);
  el.scrollTo({ top: 0, behavior: reducedMotion.value ? "auto" : "smooth" });
  // The button unmounts at the top, so keyboard and pad focus lands on the
  // first control up there instead of falling back to the body.
  if (hadFocus) {
    el.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)?.focus({
      preventScroll: true,
    });
  }
}
</script>

<template>
  <Transition name="back-to-top">
    <RBtn
      v-if="visible"
      class="back-to-top"
      variant="elevated"
      surface
      border
      rounded="circle"
      icon="mdi-chevron-up"
      :aria-label="t('gallery.back-to-top')"
      :tooltip="t('gallery.back-to-top')"
      tooltip-location="start"
      @click="scrollToTop"
    />
  </Transition>
</template>

<style scoped>
.back-to-top-enter-active,
.back-to-top-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.back-to-top-enter-from,
.back-to-top-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (prefers-reduced-motion: reduce) {
  .back-to-top-enter-active,
  .back-to-top-leave-active {
    transition: none;
  }
}
</style>
