<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import ArrowKeysIcon from "./icons/ArrowKeysIcon.vue";
import DPadIcon from "./icons/DPadIcon.vue";
import FaceButtons from "./icons/FaceButtons.vue";

interface Props {
  showNavigation?: boolean;
  showSelect?: boolean;
  showBack?: boolean;
  showToggleFavorite?: boolean;
  showMenu?: boolean;
  showDelete?: boolean;
  isModal?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  showNavigation: true,
  showSelect: true,
  showBack: true,
  showToggleFavorite: false,
  showMenu: false,
  showDelete: false,
  isModal: false,
});

const { t } = useI18n();
const hasController = ref(false);
let rafId = 0;

// Computed property to select the appropriate text color based on modal context
const textColor = computed(() =>
  props.isModal
    ? "var(--console-nav-hint-modal-text)"
    : "var(--console-nav-hint-text)",
);

// Computed property for keycap accent color
const keycapAccentColor = computed(() =>
  props.isModal
    ? "var(--console-nav-hint-modal-accent)"
    : "var(--console-nav-hint-accent)",
);

// Computed property for keycap accent color
const keycapColor = computed(() =>
  props.isModal
    ? "var(--console-nav-hint-modal-keycap)"
    : "var(--console-nav-hint-keycap)",
);

// Computed styles for keycaps
const keycapStyles = computed(() => ({
  backgroundColor: keycapAccentColor.value,
  borderColor: keycapAccentColor.value,
  color: keycapColor.value,
}));

function poll() {
  const pads = navigator.getGamepads?.() || [];
  hasController.value = pads.some((p) => p && p.connected);
  rafId = requestAnimationFrame(poll);
}

onMounted(() => {
  window.addEventListener("gamepadconnected", poll);
  window.addEventListener("gamepaddisconnected", poll);
  poll();
});

onUnmounted(() => {
  cancelAnimationFrame(rafId);
  window.removeEventListener("gamepadconnected", poll);
  window.removeEventListener("gamepaddisconnected", poll);
});
</script>

<template>
  <div
    class="flex items-center gap-6 text-[12px]"
    :style="{ color: textColor }"
  >
    <!-- Controller Mode -->
    <template v-if="hasController">
      <div v-if="showNavigation" class="flex items-center gap-2">
        <DPadIcon class="w-8 h-8 opacity-80" :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-navigation")
        }}</span>
      </div>
      <div v-if="showSelect" class="flex items-center gap-2">
        <FaceButtons highlight="south" :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-select")
        }}</span>
      </div>
      <div v-if="showBack" class="flex items-center gap-2">
        <FaceButtons highlight="east" :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-back")
        }}</span>
      </div>
      <div v-if="showToggleFavorite" class="flex items-center gap-2">
        <FaceButtons highlight="north" :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-favorite")
        }}</span>
      </div>
      <div v-if="showMenu" class="flex items-center gap-2">
        <FaceButtons highlight="west" :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-menu")
        }}</span>
      </div>
      <div v-if="showDelete" class="flex items-center gap-2">
        <FaceButtons highlight="west" :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-delete")
        }}</span>
      </div>
    </template>
    <!-- Keyboard Mode -->
    <template v-else>
      <div v-if="showNavigation" class="flex items-center gap-2">
        <ArrowKeysIcon :modal="isModal" />
        <span class="font-medium tracking-wide">{{
          t("console.nav-navigation")
        }}</span>
      </div>
      <div v-if="showSelect" class="flex items-center gap-2">
        <span class="keycap" :style="keycapStyles">Enter</span>
        <span class="font-medium tracking-wide">{{
          t("console.nav-select")
        }}</span>
      </div>
      <div v-if="showBack" class="flex items-center gap-2">
        <span class="keycap" :style="keycapStyles">Bkspc</span>
        <span class="font-medium tracking-wide">{{
          t("console.nav-back")
        }}</span>
      </div>
      <div v-if="showToggleFavorite" class="flex items-center gap-2">
        <span class="keycap" :style="keycapStyles">F</span>
        <span class="font-medium tracking-wide">{{
          t("console.nav-favorite")
        }}</span>
      </div>
      <div v-if="showMenu" class="flex items-center gap-2">
        <span class="keycap" :style="keycapStyles">X</span>
        <span class="font-medium tracking-wide">{{
          t("console.nav-menu")
        }}</span>
      </div>
      <div v-if="showDelete" class="flex items-center gap-2">
        <span class="keycap" :style="keycapStyles">X</span>
        <span class="font-medium tracking-wide">{{
          t("console.nav-delete")
        }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.keycap {
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 10px;
  font-family:
    ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo,
    monospace;
  font-weight: 700;
  letter-spacing: 0.05em;
  border: 1px solid;
  opacity: 0.9;
}
</style>
