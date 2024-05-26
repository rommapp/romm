<script setup lang="ts">
import {
  reactive,
  computed,
  ref,
  onMounted,
  onBeforeUnmount,
  useAttrs,
} from "vue";

const props = defineProps<{
  src: string;
  placeholder: string;
  srcset?: string;
  intersectionOptions?: IntersectionObserverInit;
  usePicture?: boolean;
}>();

const emit = defineEmits(["load", "error", "intersect"]);
const attrs = useAttrs();

const root = ref<HTMLPictureElement | HTMLImageElement | null>(null);
const state = reactive<{
  observer: IntersectionObserver | null;
  intersected: boolean;
  loaded: boolean;
}>({
  observer: null,
  intersected: false,
  loaded: false,
});

const srcImage = computed(() =>
  state.intersected && props.src ? props.src : props.placeholder
);
const srcsetImage = computed(() =>
  state.intersected && props.srcset ? props.srcset : ""
);

const load = () => {
  if (root.value && root.value.getAttribute("src") !== props.placeholder) {
    state.loaded = true;
    emit("load", root.value);
  }
};
const error = () => emit("error", root.value);

// Hooks
onMounted(() => {
  if ("IntersectionObserver" in window) {
    state.observer = new IntersectionObserver((entries) => {
      const image = entries[0];
      if (image.isIntersecting) {
        state.intersected = true;
        state.observer?.disconnect();
        emit("intersect");
      }
    }, props.intersectionOptions ?? {});

    if (root.value) state.observer.observe(root.value);
  }
});

onBeforeUnmount(() => {
  if ("IntersectionObserver" in window && state.observer) {
    state.observer.disconnect();
  }
});
</script>

<template>
  <picture v-if="usePicture" ref="root" @load="load">
    <slot v-if="state.intersected"></slot>
    <img
      v-else
      :src="srcImage"
      :srcSet="srcsetImage"
      v-bind="attrs"
      :class="[attrs.class, 'v-responsive v-img v-lazy-image', { 'v-lazy-image-loaded': state.loaded }]"
      @load="load"
      @error="error"
    >
      <slot />
    </img>
  </picture>
  <img
    v-else
    ref="root"
    :src="srcImage"
    :srcSet="srcsetImage"
    v-bind="attrs"
    :class="[attrs.class, 'v-responsive v-img v-lazy-image', { 'v-lazy-image-loaded': state.loaded }]"
    @load="load"
    @error="error"
  >
    <slot />
  </img>
</template>
