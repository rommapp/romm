<template>
  <button
    ref="el"
    class="relative w-[280px] h-[160px] rounded-xl border-2 border-white/10 cursor-pointer overflow-hidden shrink-0 shadow-[0_4px_20px_rgba(0,0,0,0.3),_inset_0_1px_0_rgba(255,255,255,0.1)] transition-all"
    :class="{
      '-translate-y-[2px] scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--system-accent),_0_0_16px_var(--system-accent)]': selected,
    }"
    :style="{ '--system-bg': theme.background, '--system-accent': theme.accent }"
    @click="emit('click')"
    @mouseenter="emit('mouseenter')"
    @focus="emit('focus')"
  >
    <div
      class="absolute inset-0"
      :style="{ background: 'var(--system-bg)', opacity: 0.9 }"
    />
    <div class="absolute inset-0 flex items-center justify-center">
      <img
        v-if="hasImage && imageLoaded"
        :src="theme.image"
        :alt="theme.name"
        class="w-full h-full object-cover"
        @error="imageLoaded=false"
      >
      <div
        v-else
        class="absolute inset-0 flex flex-col items-center justify-center"
        :style="{ background:'var(--system-bg)' }"
      >
        <div class="text-2xl mb-2">
          🎮
        </div>
        <div class="text-white font-bold text-center">
          {{ theme.shortName }}
        </div>
      </div>
    </div>
    <div
      class="absolute inset-0 opacity-0 pointer-events-none"
      :style="{ background: 'radial-gradient(circle at center, var(--system-accent) 0%, transparent 70%)' }"
      :class="{ 'opacity-10': selected }"
    />
    <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/30 to-transparent px-4 py-2 z-10">
      <div class="text-sm text-white/90 text-center font-medium">
        {{ system.rom_count || 0 }} games
      </div>
    </div>
  </button>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-explicit-any */
import { computed, onMounted, ref } from 'vue';

const props = defineProps<{ system: any; index: number; selected?: boolean }>();
const emit = defineEmits(['click','mouseenter','focus']);
const imageLoaded = ref(true);
const el = ref<HTMLElement>();

onMounted(() => {
  if (el.value) {
    (window as any).systemCardElements = (window as any).systemCardElements || [];
    (window as any).systemCardElements[props.index] = el.value;
  }
});

const systemThemes: Record<string, any> = {
  arcade: { name: 'Arcade', shortName: 'Arcade', image: '/systems/arcade.webp', background: 'linear-gradient(135deg, #d73266 0%, #8b1538 100%)', accent: '#d73266' },
  mame: { name: 'Arcade', shortName: 'MAME', image: '/systems/arcade.webp', background: 'linear-gradient(135deg, #d73266 0%, #8b1538 100%)', accent: '#d73266' },
  nes: { name: 'Nintendo Entertainment System', shortName: 'NES', image: '/systems/nes.webp', background: 'linear-gradient(135deg, #cc2936 0%, #8b1538 100%)', accent: '#cc2936' },
  snes: { name: 'Super Nintendo', shortName: 'SNES', image: '/systems/snes.webp', background: 'linear-gradient(135deg, #e22828 0%, #f81414 100%)', accent: '#e22828' },
  n64: { name: 'Nintendo 64', shortName: 'N64', image: '/systems/n64.webp', background: 'linear-gradient(135deg, #ffd700 0%, #ff8c00 100%)', accent: '#ffd700' },
  gb: { name: 'Game Boy', shortName: 'GB', image: '/systems/gbc.webp', background: 'linear-gradient(135deg, #8fbc8f 0%, #556b2f 100%)', accent: '#8fbc8f' },
  gba: { name: 'Game Boy Advance', shortName: 'GBA', image: '/systems/gba.webp', background: 'linear-gradient(135deg, #9370db 0%, #4b0082 100%)', accent: '#9370db' },
  gbc: { name: 'Game Boy Color', shortName: 'GBC', image: '/systems/gbc.webp', background: 'linear-gradient(135deg, #20b2aa 0%, #008b8b 100%)', accent: '#20b2aa' },
  genesis: { name: 'Sega Genesis', shortName: 'Genesis', image: '/systems/genesis.webp', background: 'linear-gradient(135deg, #1e90ff 0%, #0f4c75 100%)', accent: '#1e90ff' },
  megadrive: { name: 'Sega Genesis', shortName: 'Genesis', image: '/systems/genesis.webp', background: 'linear-gradient(135deg, #1e90ff 0%, #0f4c75 100%)', accent: '#1e90ff' },
  sms: { name: 'Sega Master System', shortName: 'SMS', image: undefined, background: 'linear-gradient(135deg, #ff6347 0%, #dc143c 100%)', accent: '#ff6347' },
  psx: { name: 'Sony PlayStation', shortName: 'PSX', image: undefined, background: 'linear-gradient(135deg, #4169e1 0%, #191970 100%)', accent: '#4169e1' },
  psp: { name: 'Sony PSP', shortName: 'PSP', image: '/systems/psp.webp', background: 'linear-gradient(135deg, #4169e1 0%, #191970 100%)', accent: '#4169e1' },
};

const theme = computed(() => {
  const s: any = props.system || {};
  return systemThemes[s.slug] || systemThemes[s.fs_slug] || { name: s.name, shortName: s.name, image: undefined, background: 'linear-gradient(135deg, #2b3242 0%, #1b2233 100%)', accent: '#f8b400' };
});

const hasImage = computed(() => Boolean((theme.value as any).image));
</script>
