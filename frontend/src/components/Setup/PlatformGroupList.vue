<script setup lang="ts">
import { computed } from "vue";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import type { Platform } from "@/stores/platforms";

const props = defineProps<{
  groupedPlatforms: [string, Platform[]][];
  selectedPlatforms?: string[];
  showCheckboxes?: boolean;
  keyPrefix?: string;
  baseIndex?: number;
}>();

const emit = defineEmits<{
  "update:selectedPlatforms": [value: string[]];
}>();

const selectedPlatformsModel = computed({
  get: () => props.selectedPlatforms ?? [],
  set: (value: string[]) => emit("update:selectedPlatforms", value),
});

// Count selected platforms in a group
const countSelectedInGroup = (platforms: Platform[]) => {
  return platforms.filter((p) =>
    selectedPlatformsModel.value.includes(p.fs_slug),
  ).length;
};
</script>

<template>
  <v-expansion-panels
    multiple
    class="bg-transparent"
    elevation="0"
    variant="accordion"
  >
    <v-expansion-panel
      v-for="([groupName, platforms], index) in groupedPlatforms"
      :key="`${keyPrefix}-${groupName}`"
      :value="baseIndex ? index + baseIndex : index"
      class="bg-transparent"
    >
      <v-expansion-panel-title class="text-white text-shadow">
        <strong>{{ groupName }}</strong>
        <span class="ml-2 text-caption text-grey"
          >({{ platforms.length }})</span
        >
        <v-chip
          v-if="showCheckboxes && countSelectedInGroup(platforms) > 0"
          size="x-small"
          color="primary"
          class="ml-2"
        >
          {{ countSelectedInGroup(platforms) }} selected
        </v-chip>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <v-list lines="two" class="py-1 px-0 bg-transparent">
          <PlatformListItem
            v-for="platform in platforms"
            :key="platform.fs_slug"
            :platform="platform"
            :show-rom-count="false"
          >
            <template v-if="showCheckboxes" #prepend>
              <v-checkbox
                v-model="selectedPlatformsModel"
                :value="platform.fs_slug"
                hide-details
                density="compact"
                class="mr-2"
              />
            </template>
          </PlatformListItem>
        </v-list>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>
