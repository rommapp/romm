<script setup lang="ts">
import { computed, onMounted, useTemplateRef } from "vue";
import { useI18n } from "vue-i18n";
import FallbackSystemCard from "@/console/components/FallbackSystemCard.vue";
import { systemElementRegistry } from "@/console/composables/useElementRegistry";
import { useThemeAssets } from "@/console/composables/useThemeAssets";
import { getPlatformTheme } from "@/console/constants/platforms";
import type { Platform } from "@/stores/platforms";

const { t } = useI18n();
const props = defineProps<{
  platform: Platform;
  index: number;
  selected?: boolean;
}>();
const emit = defineEmits(["click", "mouseenter", "focus"]);
const systemCardRef = useTemplateRef<HTMLButtonElement>("system-card-ref");
const { getSystemImagePath } = useThemeAssets();

onMounted(() => {
  if (systemCardRef.value) {
    systemElementRegistry.registerElement(props.index, systemCardRef.value);
  }
});

const theme = computed(() => {
  const platformTheme = getPlatformTheme(props.platform.slug);
  if (platformTheme) {
    return {
      name: platformTheme.label,
      image: getSystemImagePath(props.platform.slug).value,
      background: platformTheme.background,
      accent: platformTheme.accent,
    };
  }

  return {
    name: props.platform.name,
    image: undefined,
    background: "var(--console-system-card-bg-fallback)",
    accent: "var(--console-system-accent-fallback)",
  };
});
</script>

<template>
  <button
    ref="system-card-ref"
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
      class="absolute inset-0 m-px!"
      :style="{ background: 'var(--system-bg)', opacity: 0.9 }"
    />
    <div class="absolute inset-0 flex items-center justify-center">
      <v-img
        v-if="theme.image"
        :src="theme.image"
        :alt="theme.name"
        class="w-full h-full object-cover"
      >
        <template #error>
          <FallbackSystemCard :platform-name="platform.name" />
        </template>
      </v-img>
      <FallbackSystemCard v-else :platform-name="platform.name" />
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
      <div
        class="text-sm text-center font-medium"
        :style="{ color: 'var(--console-system-card-text)' }"
      >
        {{ t("console.games-n", platform.rom_count || 0) }}
      </div>
    </div>
  </button>
</template>
