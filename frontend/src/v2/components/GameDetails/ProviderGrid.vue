<script setup lang="ts">
// ProviderGrid — Metadata-tab grid showing every configured provider.
// Linked providers come first, unlinked ones follow in a muted row so
// users can see what's missing. Card visuals are owned by ProviderCard.
import { computed } from "vue";
import type { DetailedRom } from "@/stores/roms";
import ProviderCard from "@/v2/components/GameDetails/ProviderCard.vue";
import { PROVIDERS, providerId } from "@/v2/components/GameDetails/providers";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRom }>();

type Entry = {
  name: string;
  accent: string;
  logo: string | null;
  id: string | number | null;
  href: string | null;
};

const entries = computed<Entry[]>(() => {
  const all = PROVIDERS.map<Entry>((p) => {
    const id = providerId(props.rom, p);
    return {
      name: p.name,
      accent: p.color,
      logo: p.logo,
      id,
      href: id !== null && p.url ? p.url(id) : null,
    };
  });
  // Linked first; the cards know how to dim themselves when unlinked.
  return all.sort((a, b) => Number(b.id !== null) - Number(a.id !== null));
});
</script>

<template>
  <div class="provider-grid">
    <ProviderCard
      v-for="e in entries"
      :key="e.name"
      :name="e.name"
      :accent="e.accent"
      :logo="e.logo"
      :id="e.id"
      :href="e.href"
    />
  </div>
</template>

<style scoped>
.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
</style>
