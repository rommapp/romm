<template>
  <div class="min-h-screen text-white console-root">
    <router-view />
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, provide } from 'vue';
import './index.css';
import { InputBus, InputBusSymbol } from '@/console/input/bus';
import { attachKeyboard } from '@/console/input/keyboard';
import { attachGamepad } from '@/console/input/gamepad';

const bus = new InputBus();
provide(InputBusSymbol, bus);

let detachKeyboard: (() => void) | null = null;
let detachGamepad: (() => void) | null = null;
onMounted(() => document.body.classList.add('console-mode'));
onMounted(() => {
  // Establish a root input scope so child views can subscribe safely
  bus.pushScope();
  detachKeyboard = attachKeyboard(bus);
  detachGamepad = attachGamepad(bus);
});
onUnmounted(() => {
  document.body.classList.remove('console-mode');
  // teardown input attachments
  detachKeyboard?.();
  detachGamepad?.();
});
</script>
<style></style>
