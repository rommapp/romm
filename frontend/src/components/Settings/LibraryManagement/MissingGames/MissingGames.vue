<script setup lang="ts">
import RomListItem from "@/components/common/Game/ListItem.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";

const props = defineProps<{ missingGames: SimpleRom[]; loading: boolean }>();
const { mdAndUp } = useDisplay();
const missingGamesByPlatform = computed(() => {
  const grouped = new Map<string, { platform: any; roms: SimpleRom[] }>();

  props.missingGames.forEach((game) => {
    const platformKey = game.platform_id.toString();
    if (!grouped.has(platformKey)) {
      grouped.set(platformKey, {
        platform: {
          id: game.platform_id,
          name: game.platform_display_name,
          slug: game.platform_slug,
          fs_slug: game.platform_fs_slug,
        },
        roms: [],
      });
    }
    grouped.get(platformKey)!.roms.push(game);
  });

  return Array.from(grouped.values());
});
const panels = ref<number[]>([]);
</script>
<template>
  <v-row :class="{ 'mx-10': mdAndUp }" no-gutters>
    <v-col cols="12" class="px-2">
      <h1 class="text-h6">
        <span class="text-accent">{{ props.missingGames.length }}</span> Missing
        games from
        <span class="text-accent">{{ missingGamesByPlatform.length }}</span>
        {{ missingGamesByPlatform.length !== 1 ? "Platforms" : "Platform" }}
        <v-progress-circular
          v-if="props.loading"
          :width="2"
          :size="25"
          color="primary"
          class="ml-2"
          indeterminate
        />
      </h1>
    </v-col>
    <v-col cols="12">
      <v-expansion-panels
        v-model="panels"
        multiple
        flat
        variant="accordion"
        class="mt-2"
      >
        <v-expansion-panel
          v-for="platformGroup in missingGamesByPlatform"
          :key="platformGroup.platform.id"
        >
          <v-expansion-panel-title static>
            <v-list-item class="pa-0">
              <template #prepend>
                <v-avatar rounded="0" size="40">
                  <platform-icon
                    :key="platformGroup.platform.slug"
                    :slug="platformGroup.platform.slug"
                    :name="platformGroup.platform.name"
                    :fs-slug="platformGroup.platform.fs_slug"
                  />
                </v-avatar>
              </template>
              {{ platformGroup.platform.name }}
              <template #append>
                <v-chip class="ml-3" color="accent" size="x-small" label>{{
                  platformGroup.roms.length
                }}</v-chip>
              </template>
            </v-list-item>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="bg-toplayer">
            <rom-list-item
              v-for="rom in platformGroup.roms"
              :key="rom.id"
              class="pa-4"
              :rom="rom"
              with-link
              with-filename
            >
            </rom-list-item>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-col>
  </v-row>
</template>
<style lang="css">
.v-expansion-panel-text__wrapper {
  padding: 0px;
}
</style>
