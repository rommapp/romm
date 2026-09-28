<script setup lang="ts">
// BackToTopButton: floating control that returns a long gallery scroll to
// its top, shown once the viewer is more than a viewport down.
import { RBtn } from "@v2/lib";
import { useResizeObserver } from "@vueuse/core";
import { computed, ref, toRef, watch } from "vue";
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

const viewportHeight = ref(0);
useResizeObserver(toRef(props, "scroller"), () => {
  viewportHeight.value = props.scroller?.clientHeight ?? 0;
});
watch(
  () => props.scroller,
  (el) => {
    viewportHeight.value = el?.clientHeight ?? 0;
  },
  { immediate: true },
);

const visible = computed(
  () => !!props.scroller && props.scrollTop > viewportHeight.value,
);

// Set while a keyboard or pad user rides the scroll up; cleared once focus
// lands on a control at the top.
const focusOnArrival = ref(false);
watch(
  () => props.scrollTop,
  (top) => {
    if (!focusOnArrival.value || top > 0) return;
    focusOnArrival.value = false;
    props.scroller
      ?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      ?.focus({ preventScroll: true });
  },
);

function scrollToTop(event: MouseEvent) {
  const el = props.scroller;
  if (!el) return;
  emit("scroll-to-top");
  const hadFocus =
    event.currentTarget instanceof HTMLElement &&
    event.currentTarget.contains(document.activeElement);
  // The button unmounts at the top, so keyboard and pad focus moves to the
  // first control there. Rows mid-scroll may be virtualised away, so wait.
  focusOnArrival.value = hadFocus;
  el.scrollTo({ top: 0, behavior: reducedMotion.value ? "auto" : "smooth" });
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
