<script setup lang="ts">
import { useIdle, useLocalStorage } from "@vueuse/core";
import { onBeforeMount, onMounted, onUnmounted, provide } from "vue";
import { type RouteLocationNormalized } from "vue-router";
import { useRouter } from "vue-router";
import { useConsoleTheme } from "@/console/composables/useConsoleTheme";
import { InputBus, InputBusSymbol } from "@/console/input/bus";
import { attachGamepad } from "@/console/input/gamepad";
import { attachKeyboard } from "@/console/input/keyboard";
import { ROUTES } from "@/plugins/router";
import storeCollections from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";

const router = useRouter();
const bus = new InputBus();
const themeStore = useConsoleTheme();
provide(InputBusSymbol, bus);

const navigationStore = storeNavigation();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();

const showVirtualCollections = useLocalStorage(
  "settings.showVirtualCollections",
  true,
);
const virtualCollectionTypeRef = useLocalStorage(
  "settings.virtualCollectionType",
  "collection",
);

// Define route hierarchy for transition direction logic
const routeHierarchy = {
  [ROUTES.CONSOLE_HOME]: 0,
  [ROUTES.CONSOLE_PLATFORM]: 1,
  [ROUTES.CONSOLE_COLLECTION]: 1,
  [ROUTES.CONSOLE_SMART_COLLECTION]: 1,
  [ROUTES.CONSOLE_VIRTUAL_COLLECTION]: 1,
  [ROUTES.CONSOLE_ROM]: 2,
  [ROUTES.CONSOLE_PLAY]: 3,
};

function getTransitionName(route: RouteLocationNormalized): string {
  const currentName = route.name as string;
  const currentLevel =
    routeHierarchy[currentName as keyof typeof routeHierarchy] ?? 1;

  const previousRoute = router.options.history.state.back;
  const previousLevel = previousRoute
    ? (routeHierarchy[previousRoute as keyof typeof routeHierarchy] ?? 1)
    : 0;

  if (
    currentName === ROUTES.CONSOLE_PLAY ||
    previousRoute === ROUTES.CONSOLE_PLAY
  ) {
    return currentLevel > previousLevel ? "slide-up" : "slide-down";
  }

  if (currentLevel > previousLevel) return "slide-left";
  return currentLevel < previousLevel ? "slide-right" : "fade";
}

const { idle: mouseIdle } = useIdle(100, {
  events: ["mousemove", "mousedown", "wheel", "touchstart"],
});

let detachKeyboard: (() => void) | null = null;
let detachGamepad: (() => void) | null = null;

onBeforeMount(() => {
  platformsStore.fetchPlatforms();
  collectionsStore.fetchCollections();
  collectionsStore.fetchSmartCollections();
  if (showVirtualCollections) {
    collectionsStore.fetchVirtualCollections(virtualCollectionTypeRef.value);
  }

  navigationStore.reset();
});

onMounted(() => {
  themeStore.initializeTheme();

  // Establish a root input scope so child views can subscribe safely
  bus.pushScope();
  detachKeyboard = attachKeyboard(bus);
  detachGamepad = attachGamepad(bus);
});

onUnmounted(() => {
  detachKeyboard?.();
  detachGamepad?.();
});
</script>

<template>
  <div
    class="min-h-screen console-root relative"
    :style="{ color: 'var(--console-text-primary)' }"
  >
    <!-- Shield overlay to neutralize mouse input while hidden; movement wakes it -->
    <div
      v-if="!mouseIdle"
      class="fixed inset-0 z-50 cursor-none"
      aria-hidden="true"
      @mousedown.prevent
      @mouseup.prevent
      @click.prevent
      @pointerdown.prevent
      @pointerup.prevent
      @wheel.prevent
      @contextmenu.prevent
      @dragstart.prevent
    />
    <router-view v-slot="{ Component, route }">
      <transition :name="getTransitionName(route)" mode="out-in" appear>
        <component :is="Component" :key="route.path" />
      </transition>
    </router-view>
  </div>
</template>
