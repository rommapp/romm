<script setup lang="ts">
// RExpandTransition — animates the wrapped element's height between
// `0` and its natural content height when toggled via `v-if` or
// `v-show`. Drop-in replacement for the height-collapse transition
// pattern: the consumer wraps a single child, the wrapper hooks into
// Vue's `<Transition>` and drives the height via JS so we can animate
// from a measured `scrollHeight` (CSS can't transition `height: auto`).
//
// Default behaviour:
//   • No animation on first mount (matches the height-collapse
//     convention). Pass `appear` to opt in.
//   • Reduced-motion: skip the height animation entirely; the child
//     still appears / disappears, just instantly.
//
// Usage:
//
//   <RExpandTransition>
//     <div v-if="open">Content</div>
//   </RExpandTransition>
//
//   <RExpandTransition>
//     <div v-show="open">Content</div>
//   </RExpandTransition>
//
// Only handles vertical (height) expansion — width transitions are
// rare enough to not justify a sibling primitive yet.
import { useReducedMotion } from "@/v2/composables/useReducedMotion";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Animate the child on first mount, not just on subsequent toggles. */
  appear?: boolean;
  /** Override the transition duration. Accepts any CSS time value. */
  duration?: string;
}

const props = withDefaults(defineProps<Props>(), {
  appear: false,
  duration: undefined,
});

// Cache previous inline styles per element so we can restore them
// after the transition lands — consumers may have set their own
// `height` / `overflow` for layout reasons and we don't want to clobber.
type Snapshot = { height: string; overflow: string };
const snapshots = new WeakMap<HTMLElement, Snapshot>();

function snapshot(el: HTMLElement) {
  snapshots.set(el, {
    height: el.style.height,
    overflow: el.style.overflow,
  });
}

function restore(el: HTMLElement) {
  const snap = snapshots.get(el);
  if (snap) {
    el.style.height = snap.height;
    el.style.overflow = snap.overflow;
    snapshots.delete(el);
  } else {
    el.style.height = "";
    el.style.overflow = "";
  }
  el.style.transition = "";
}

const reducedMotion = useReducedMotion();

function buildTransition(): string {
  const dur = props.duration ?? "var(--r-motion-med)";
  // Use the lib's standard ease-out so the motion vocabulary stays
  // consistent with RDialog / RMenu / RTooltip.
  return `height ${dur} var(--r-motion-ease-out)`;
}

function onEnter(el: Element, done: () => void) {
  const e = el as HTMLElement;
  if (reducedMotion.value) {
    done();
    return;
  }
  snapshot(e);
  const target = e.scrollHeight;
  e.style.overflow = "hidden";
  e.style.height = "0px";
  // Force the start frame to commit before flipping to the target.
  // Without the rAF the browser collapses both updates into one and
  // skips the animation.
  requestAnimationFrame(() => {
    e.style.transition = buildTransition();
    e.style.height = `${target}px`;
    const finish = (event: TransitionEvent) => {
      if (event.target !== e || event.propertyName !== "height") return;
      e.removeEventListener("transitionend", finish);
      restore(e);
      done();
    };
    e.addEventListener("transitionend", finish);
  });
}

function onLeave(el: Element, done: () => void) {
  const e = el as HTMLElement;
  if (reducedMotion.value) {
    done();
    return;
  }
  snapshot(e);
  const start = e.scrollHeight;
  e.style.overflow = "hidden";
  e.style.height = `${start}px`;
  // Same single-frame trick as enter — commit the start frame before
  // animating to 0, otherwise the browser fast-paths to the end value.
  requestAnimationFrame(() => {
    e.style.transition = buildTransition();
    e.style.height = "0px";
    const finish = (event: TransitionEvent) => {
      if (event.target !== e || event.propertyName !== "height") return;
      e.removeEventListener("transitionend", finish);
      restore(e);
      done();
    };
    e.addEventListener("transitionend", finish);
  });
}
</script>

<template>
  <Transition :appear="appear" :css="false" @enter="onEnter" @leave="onLeave">
    <slot />
  </Transition>
</template>
