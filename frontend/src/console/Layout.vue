<template>
  <div class="min-h-screen text-white console-root relative">
    <!-- Shield overlay to neutralize mouse input while hidden; movement wakes it -->
    <div
      v-if="mouseHidden"
      class="fixed inset-0 z-50 cursor-none"
      @mousemove="onMouseActivity"
      @mousedown.prevent
      @click.prevent
      @wheel.prevent
      @contextmenu.prevent
    />
    <router-view />
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, provide, ref } from 'vue';
import './index.css';
import { InputBus, InputBusSymbol } from '@/console/input/bus';
import { attachKeyboard } from '@/console/input/keyboard';
import { attachGamepad } from '@/console/input/gamepad';

const bus = new InputBus();
provide(InputBusSymbol, bus);

let detachKeyboard: (() => void) | null = null;
let detachGamepad: (() => void) | null = null;
const mouseHidden = ref(false);
let idleTimer: number | undefined;
const onMouseActivity = () => {
  mouseHidden.value = false;
  window.clearTimeout(idleTimer);
  idleTimer = window.setTimeout(() => { mouseHidden.value = true; }, 2000);
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
onUnmounted(() => {
  document.body.classList.remove('console-mode');
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
<style></style>
