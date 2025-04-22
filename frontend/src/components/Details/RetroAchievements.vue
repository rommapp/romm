<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";

// Props
defineProps<{ rom: DetailedRom }>();
</script>
<template>
  <v-list v-if="rom.merged_ra_metadata?.achievements" class="bg-background">
    <v-list-item
      v-for="achievement in rom.merged_ra_metadata?.achievements.sort(
        (a, b) => (a.display_order ?? 0) - (b.display_order ?? 0),
      )"
      :title="achievement.title?.toString()"
      :subtitle="achievement.description?.toString()"
      class="mb-2 py-4 rounded bg-toplayer"
    >
      <template #prepend>
        <v-avatar v-if="achievement.badge_path_lock" rounded="0">
          <v-img :src="achievement.badge_path_lock" />
        </v-avatar>
      </template>
    </v-list-item>
  </v-list>
</template>
