<template>
  <div class="min-h-screen text-white console-root relative">
    <!-- Shield overlay to neutralize mouse input while hidden; movement wakes it -->
    <div
      v-if="mouseHidden"
      class="fixed inset-0 z-50 cursor-none"
      aria-hidden="true"
      @mousemove="onMouseActivity"
      @pointermove="onMouseActivity"
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
      <transition
        :name="getTransitionName(route)"
        mode="out-in"
        appear
      >
        <component 
          :is="Component" 
          :key="route.path" 
        />
      </transition>
    </router-view>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, provide, ref, watch } from 'vue';
import { useRoute, type RouteLocationNormalized } from 'vue-router';
import './index.css';
import { InputBus, InputBusSymbol } from '@/console/input/bus';
import { attachKeyboard } from '@/console/input/keyboard';
import { attachGamepad } from '@/console/input/gamepad';

const currentRoute = useRoute();
const bus = new InputBus();
provide(InputBusSymbol, bus);

// Define route hierarchy for transition direction logic
const routeHierarchy = {
  'console-home': 0,
  'console-platform': 1,
  'console-collection': 1,
  'console-rom': 2,
  'console-play': 3,
};

let previousRoute: string | null = null;

// Determine transition based on navigation direction and route type
function getTransitionName(route: RouteLocationNormalized): string {
  const currentName = route.name as string;
  const currentLevel = routeHierarchy[currentName as keyof typeof routeHierarchy] ?? 1;
  const previousLevel = previousRoute ? (routeHierarchy[previousRoute as keyof typeof routeHierarchy] ?? 1) : 0;
  
  // Special case for play mode (slide up/down)
  if (currentName === 'console-play' || previousRoute === 'console-play') {
    return currentLevel > previousLevel ? 'slide-up' : 'slide-down';
  }
  
  // General navigation (slide left/right)
  if (currentLevel > previousLevel) {
    return 'slide-left'; // Going deeper (forward)
  } else if (currentLevel < previousLevel) {
    return 'slide-right'; // Going back
  } else {
    return 'fade'; // Same level or first load
  }
}

// Track route changes for transition direction
watch(() => currentRoute.name, (newName, oldName) => {
  if (oldName) {
    previousRoute = oldName as string;
  }
});

let detachKeyboard: (() => void) | null = null;
let detachGamepad: (() => void) | null = null;
const mouseHidden = ref(false);
let idleTimer: number | undefined;
const HIDE_DELAY_MS = 100;
const onMouseActivity = () => {
  // Show cursor (remove shield) then schedule hide
  if (mouseHidden.value) mouseHidden.value = false;
  window.clearTimeout(idleTimer);
  idleTimer = window.setTimeout(() => { mouseHidden.value = true; }, HIDE_DELAY_MS);
};
const docHandler = () => onMouseActivity();
onMounted(() => document.body.classList.add('console-mode'));
onMounted(() => {
  // Establish a root input scope so child views can subscribe safely
  bus.pushScope();
  detachKeyboard = attachKeyboard(bus);
  detachGamepad = attachGamepad(bus);
  // Mouse idle/hide across all console views
  onMouseActivity();
  document.addEventListener('mousemove', docHandler, { passive: true });
  document.addEventListener('mousedown', docHandler, { passive: true });
  document.addEventListener('wheel', docHandler, { passive: true });
  document.addEventListener('touchstart', docHandler, { passive: true });
});
// Toggle a body class for global cursor hiding (covers any nested explicit cursor styles)
watch(mouseHidden, hidden => {
  if (hidden) document.body.classList.add('mouse-hidden');
  else document.body.classList.remove('mouse-hidden');
});
// Ensure correct initial class
watch(mouseHidden, () => {}, { immediate: true });
onUnmounted(() => {
  document.body.classList.remove('console-mode');
  document.body.classList.remove('mouse-hidden');
  // teardown input attachments
  detachKeyboard?.();
  detachGamepad?.();
  document.removeEventListener('mousemove', docHandler as EventListener);
  document.removeEventListener('mousedown', docHandler as EventListener);
  document.removeEventListener('wheel', docHandler as EventListener);
  document.removeEventListener('touchstart', docHandler as EventListener);
  window.clearTimeout(idleTimer);
});
</script>
<style>
body.console-mode.mouse-hidden, body.console-mode.mouse-hidden * { cursor: none !important; }
</style>
