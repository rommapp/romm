<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-explicit-any */
import { computed, onMounted, ref } from "vue";
import { getPlatformTheme } from "@/console/constants/platforms";

const props = defineProps<{ system: any; index: number; selected?: boolean }>();
const emit = defineEmits(["click", "mouseenter", "focus"]);
const imageLoaded = ref(true);
const el = ref<HTMLElement>();

onMounted(() => {
  if (el.value) {
    (window as any).systemCardElements =
      (window as any).systemCardElements || [];
    (window as any).systemCardElements[props.index] = el.value;
  }
});

const theme = computed(() => {
  const s: any = props.system || {};
  const def = getPlatformTheme(s.slug);
  if (def) {
    return {
      name: def.label,
      shortName: def.shortName || def.label,
      image: def.image,
      background: def.background || "linear-gradient(135deg,#2b3242,#1b2233)",
      accent: def.accent || "#f8b400",
    };
  }
  return {
    name: s.name,
    shortName: s.name,
    image: undefined,
    background: "linear-gradient(135deg, #2b3242 0%, #1b2233 100%)",
    accent: "#f8b400",
  };
});

const hasImage = computed(() => Boolean((theme.value as any).image));
</script>

<template>
  <button
    ref="el"
    class="relative w-[280px] h-[160px] rounded-xl border-2 border-white/10 cursor-pointer overflow-hidden shrink-0 shadow-[0_4px_20px_rgba(0,0,0,0.3),_inset_0_1px_0_rgba(255,255,255,0.1)] transition-all"
    :class="{
      '-translate-y-[2px] scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--system-accent),_0_0_16px_var(--system-accent)]':
        selected,
    }"
    :style="{
      '--system-bg': theme.background,
      '--system-accent': theme.accent,
    }"
    @click="emit('click')"
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
        @error="imageLoaded = false"
      />
      <div
        v-else
        class="absolute inset-0 flex flex-col items-center justify-center"
        :style="{ background: 'var(--system-bg)' }"
      >
        <div class="text-2xl mb-2">🎮</div>
        <div class="text-white font-bold text-center">
          {{ theme.shortName }}
        </div>
      </div>
    </div>
    <div
      class="absolute inset-0 opacity-0 pointer-events-none"
      :style="{
        background:
          'radial-gradient(circle at center, var(--system-accent) 0%, transparent 70%)',
      }"
      :class="{ 'opacity-10': selected }"
    />
    <div
      class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/30 to-transparent px-4 py-2 z-10"
    >
      <div class="text-sm text-white/90 text-center font-medium">
        {{ system.rom_count || 0 }} games
      </div>
    </div>
  </button>
</template>
