<template>
  <div class="fixed bottom-4 right-20 flex items-center gap-10 bg-black/80 px-8 py-3 rounded-lg backdrop-blur text-white/70 text-[12px] z-[100] pointer-events-none select-none border border-white/10">
    <!-- Controller Mode -->
    <template v-if="hasController">
      <div class="flex items-center gap-2">
        <DPadIcon class="w-8 h-8 opacity-80" />
        <span class="font-medium tracking-wide">Navigation</span>
      </div>
      <div class="flex items-center gap-2">
        <FaceButtons highlight="south" />
        <span class="font-medium tracking-wide">Select</span>
      </div>
      <div class="flex items-center gap-2">
        <FaceButtons highlight="east" />
        <span class="font-medium tracking-wide">Back</span>
      </div>
    </template>
    <!-- Keyboard Mode -->
    <template v-else>
      <div class="flex items-center gap-2">
        <ArrowKeysIcon />
        <span class="font-medium tracking-wide">Navigation</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="keycap">Enter</span>
        <span class="font-medium tracking-wide">Select</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="keycap">Bkspc</span>
        <span class="font-medium tracking-wide">Back</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, defineComponent, h } from 'vue';
/* eslint-disable vue/one-component-per-file */

const hasController = ref(false);
let rafId = 0;

function poll(){
  const pads = navigator.getGamepads?.() || [];
  hasController.value = pads.some(p => p && p.connected);
  rafId = requestAnimationFrame(poll);
}
onMounted(() => {
  window.addEventListener('gamepadconnected', pollOnce);
  window.addEventListener('gamepaddisconnected', pollOnce);
  poll();
});
onUnmounted(() => {
  cancelAnimationFrame(rafId);
  window.removeEventListener('gamepadconnected', pollOnce);
  window.removeEventListener('gamepaddisconnected', pollOnce);
});
function pollOnce(){ poll(); }

// Icons rendered via render functions (no runtime template compilation needed)
const DPadIcon = defineComponent({
  name: 'DPadIcon',
  setup() {
    return () => h('svg', { viewBox: '0 0 40 40', class: 'text-white/70', fill: 'none' }, [
      h('rect', { x:16, y:4,  width:8, height:12, rx:2, class:'fill-white/70' }),
      h('rect', { x:16, y:24, width:8, height:12, rx:2, class:'fill-white/70' }),
      h('rect', { x:4,  y:16, width:12, height:8, rx:2, class:'fill-white/70' }),
      h('rect', { x:24, y:16, width:12, height:8, rx:2, class:'fill-white/70' }),
      h('rect', { x:16, y:16, width:8, height:8, rx:2, class:'fill-white/40' }),
    ]);
  },
});

const FaceButtons = defineComponent({
  name: 'FaceButtons',
  props: { highlight: { type: String, default: 'south' } },
  setup(props) {
    // Render as SVG for crisp alignment; monochrome circles, filled highlight
    const mapping: Record<string,{cx:number; cy:number}> = {
      north: { cx: 12, cy: 4 },
      south: { cx: 12, cy: 20 },
      west:  { cx: 4,  cy: 12 },
      east:  { cx: 20, cy: 12 },
    };
    const order = ['north','south','west','east'] as const;
    return () => h('svg', { viewBox: '0 0 24 24', class: 'w-8 h-8 text-white/70 translate-y-[1px]' },
      order.map(b => h('circle', {
        key: b,
        cx: mapping[b].cx,
        cy: mapping[b].cy,
        r: 4,
        class: b === props.highlight ? 'fill-white/70' : 'fill-white/15',
      }))
    );
  },
});

// Keyboard arrow cluster icon (render function)
const ArrowKeysIcon = defineComponent({
  name: 'ArrowKeysIcon',
  setup(){
    const key = (x:number,y:number,label:string) => h('g', [
      h('rect', { x, y, width:14, height:14, rx:3, class:'fill-white/10 stroke-white/20' }),
      h('text', { x: x+7, y: y+9, 'text-anchor':'middle', 'font-size':'8', class:'fill-white/70 select-none' }, label),
    ]);
    return () => h('svg', { viewBox:'0 0 44 30', class:'w-14 h-[28px] text-white/70' }, [
      key(15,1,'↑'),
      key(1,15,'←'),
      key(15,15,'↓'),
      key(29,15,'→'),
    ]);
  }
});
</script>

<style scoped>
.keycap { display:inline-flex; align-items:center; justify-content:center; padding:0.25rem 0.55rem; border-radius:0.375rem; border:1px solid rgba(255,255,255,0.25); background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.85); font-weight:500; line-height:1; font-size:12px; box-shadow:0 2px 0 0 rgba(255,255,255,0.12);} 
</style>
