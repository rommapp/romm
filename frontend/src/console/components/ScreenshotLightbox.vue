<script setup lang="ts">
import { useActiveElement } from "@vueuse/core";
import { computed, onMounted, ref } from "vue";
import NavigationText from "./NavigationText.vue";

const props = defineProps<{ urls: string[]; startIndex?: number }>();
const emit = defineEmits(["update:modelValue", "close"]);

const carouselIndex = ref(props.startIndex);
const activeElement = useActiveElement();

const isOpen = computed({
  get: () => true,
  set: () => close(),
});

const iconColor = computed(() => {
  const computedStyle = getComputedStyle(document.documentElement);
  return (
    computedStyle.getPropertyValue("--console-modal-header-bg").trim() ||
    "#000000"
  );
});

function closeDialog() {
  emit("update:modelValue", false);
  emit("close");
}

onMounted(() => {
  activeElement.value?.blur();
});
</script>

<template>
  <v-dialog
    :model-value="isOpen"
    :width="1000"
    scroll-strategy="block"
    no-click-animation
    persistent
    z-index="9999"
    scrim="black"
    class="lightbox-dialog"
  >
    <template #default>
      <div class="lightbox-header">
        <h2 class="text-h6" :style="{ color: 'var(--console-modal-text)' }">
          Screenshots
        </h2>
        <v-btn
          icon="mdi-close"
          aria-label="Close"
          size="small"
          :color="iconColor"
          @click="closeDialog"
        />
      </div>

      <v-carousel
        v-model="carouselIndex"
        hide-delimiter-background
        delimiter-icon="mdi-square"
        show-arrows="hover"
        hide-delimiters
        class="dialog-carousel"
      >
        <template #prev="{ props: prevProps }">
          <v-btn
            v-if="urls.length > 1"
            icon="mdi-triangle"
            size="x-small"
            class="lightbox-nav-prev"
            :color="iconColor"
            @click="prevProps.onClick"
          />
        </template>

        <v-carousel-item
          v-for="screenshot in urls"
          :key="screenshot"
          :src="screenshot"
          contain
        >
          <template #placeholder>
            <div class="d-flex justify-center align-center">
              <v-progress-circular indeterminate />
            </div>
          </template>
        </v-carousel-item>

        <template #next="{ props: nextProps }">
          <v-btn
            v-if="urls.length > 1"
            icon="mdi-triangle"
            size="x-small"
            class="lightbox-nav-next"
            :color="iconColor"
            @click="nextProps.onClick"
          />
        </template>
      </v-carousel>

      <div class="lightbox-footer pa-4">
        <div class="d-flex justify-space-between align-center">
          <NavigationText
            :show-navigation="true"
            :show-select="false"
            :show-back="true"
            :show-toggle-favorite="false"
            :show-menu="false"
            :is-modal="true"
          />
          <div
            :style="{
              backgroundColor: 'var(--console-modal-header-bg)',
              color: 'var(--console-modal-text)',
            }"
            class="px-2 py-1 rounded-lg text-xs"
          >
            {{ carouselIndex ? carouselIndex + 1 : 1 }} /
            {{ urls.length }}
          </div>
        </div>
      </div>
    </template>
  </v-dialog>
</template>

<style>
.lightbox-dialog {
  backdrop-filter: blur(10px);
}

.lightbox-dialog .v-overlay__content {
  max-height: 80vh;
  border: 1px solid var(--console-modal-border);
  background-color: var(--console-modal-bg);
  border-radius: 16px;
  animation: slideUp 0.3s ease;
}

.lightbox-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  background-color: var(--console-modal-header-bg);
  border-bottom: 1px solid var(--console-modal-border-secondary);
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
}

.dialog-carousel {
  max-width: 1000px;
}

.lightbox-footer {
  border-top: 1px solid var(--console-modal-border-secondary);
  background-color: var(--console-modal-header-bg);
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
}

.lightbox-nav-prev {
  transform: rotate(-90deg);
}

.lightbox-nav-prev i,
.lightbox-nav-next i {
  font-size: 12px;
}

.lightbox-nav-next {
  transform: rotate(90deg);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
