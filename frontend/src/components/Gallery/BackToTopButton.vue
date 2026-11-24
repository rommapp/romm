<script setup lang="ts">
// BackToTopButton: floating control that returns a long gallery scroll to
// the page's top, shown once the viewer is more than a viewport down.
import { useEventListener, useWindowSize } from "@vueuse/core";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useReducedMotion } from "@/composables/useReducedMotion";
import { RButton } from "@/lib";
import { focusFromInput } from "@/utils/autofocus";
import { FOCUSABLE_SELECTOR } from "@/utils/spatialNav";

interface Props {
  /** The gallery, whose first control takes focus at the top. */
  root: HTMLElement | null;
  /** The document's scroll offset. */
  scrollTop: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "scroll-to-top"): void;
}>();

const { t } = useI18n();
const { enabled: reducedMotion } = useReducedMotion();
const { height: viewportHeight } = useWindowSize();

const visible = computed(() => props.scrollTop > viewportHeight.value);

// Set while a keyboard or pad user rides the scroll up; cleared once focus
// lands on a control at the top.
const focusOnArrival = ref(false);
watch(
  () => props.scrollTop,
  (top) => {
    if (!focusOnArrival.value || top > 0) return;
    focusOnArrival.value = false;
    focusFromInput(props.root?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR), {
      preventScroll: true,
    });
  },
);
// A ride that stops short of the top, or focus the user moves elsewhere
// meanwhile, cancels the handoff.
useEventListener(document, "scrollend", () => {
  if (window.scrollY > 0) focusOnArrival.value = false;
});
useEventListener(document, "focusin", () => {
  focusOnArrival.value = false;
});

function scrollToTop(event: MouseEvent) {
  emit("scroll-to-top");
  const hadFocus =
    event.currentTarget instanceof HTMLElement &&
    event.currentTarget.contains(document.activeElement);
  // The button unmounts at the top, so keyboard and pad focus moves to the
  // first control there. Rows mid-scroll may be virtualised away, so wait.
  focusOnArrival.value = hadFocus;
  window.scrollTo({
    top: 0,
    behavior: reducedMotion.value ? "auto" : "smooth",
  });
}
</script>

<template>
  <Transition name="back-to-top">
    <RButton
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
