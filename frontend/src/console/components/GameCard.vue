<template>
  <button
    ref="el"
    class="relative block bg-[var(--tile)] border-2 border-white/10 rounded-md p-0 cursor-pointer overflow-hidden shadow-[0_4px_20px_rgba(0,0,0,0.3),_inset_0_1px_0_rgba(255,255,255,0.1)] transition-all duration-200"
    :class="{
      '-translate-y-[2px] scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--accent-2),_0_0_16px_var(--accent-2)]': selected,
    }"
  @click="emit('click')"
  @mouseenter="emit('mouseenter')"
  @mouseleave="emit('mouseleave')"
  @focus="emit('focus')"
  >
    <div class="w-full h-[350px] bg-[#2b3242] relative overflow-hidden rounded">
      <img
        v-if="coverSrc"
        class="w-full h-full object-cover"
        :src="coverSrc"
        :alt="rom.name || rom.title"
        @load="emit('loaded')"
        @error="emit('loaded')"
      >
      <div
        v-else
        class="w-full h-full bg-gradient-to-b from-[#2b3242] to-[#1b2233]"
      />
      <!-- Selected highlight radial glow -->
      <div
        class="absolute inset-0 opacity-0 pointer-events-none"
        :style="{ background: 'radial-gradient(circle at center, var(--accent-2) 0%, transparent 70%)' }"
        :class="{ 'opacity-10': selected }"
      />
      <div
        v-if="!loaded"
        class="absolute inset-0 bg-gradient-to-r from-white/10 via-white/20 to-white/10 bg-[length:200%_100%] animate-[shimmer_1.2s_linear_infinite]"
      />
      <div class="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-b from-transparent to-black/75 text-[#eaeaea] text-sm leading-tight z-10">
        <div class="font-medium truncate">
          {{ rom.name || rom.title }}
        </div>
        <div
          v-if="rom.release_year || rom.developer"
          class="text-[#c8c8c8] text-xs opacity-90"
        >
          {{ rom.release_year }}
          <template v-if="rom.release_year && rom.developer">
            •
          </template>
          {{ rom.developer }}
        </div>
      </div>
    </div>
  <!-- Match SystemCard: glow is entirely via box-shadow above; no extra ring element -->
  </button>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
/* eslint-disable @typescript-eslint/no-explicit-any */
const props = defineProps<{ rom:any; index:number; selected?:boolean; loaded?:boolean; isRecent?:boolean }>();
const coverSrc = computed(() => props.rom.path_cover_large || props.rom.path_cover_small || props.rom.url_cover || props.rom.cover_url || props.rom.cover || '');
const emit = defineEmits(['click','mouseenter','mouseleave','focus','loaded']);
const el = ref<HTMLElement>();

onMounted(() => {
  if(!el.value) return;
  if(props.isRecent){
    (window as any).recentGameElements = (window as any).recentGameElements || [];
    (window as any).recentGameElements[props.index] = el.value;
  } else {
    (window as any).gameCardElements = (window as any).gameCardElements || [];
    (window as any).gameCardElements[props.index] = el.value;
  }
});
</script>

<style>
@keyframes shimmer { 0%{ background-position: 200% 0;} 100%{ background-position: -200% 0;} }
</style>
