<script setup lang="ts">
import { formatBytes } from "@/utils";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import RSection from "@/components/common/RSection.vue";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";

// Props
const props = defineProps<{
  total_filesize: number;
}>();
const { t } = useI18n();
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const orderBy = ref("name");

// Functions
const sortedPlatforms = computed(() => {
  const platforms = [...filteredPlatforms.value];
  if (orderBy.value === "size") {
    return platforms.sort(
      (a, b) => Number(b.fs_size_bytes) - Number(a.fs_size_bytes),
    );
  }
  // Default to name
  return platforms.sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
  );
});

function getPlatformPercentage(
  filesize: number | string,
  total: number,
): number {
  const size = typeof filesize === "string" ? parseInt(filesize, 10) : filesize;
  if (!total || isNaN(size)) return 0;
  return (size / total) * 100;
}
</script>

<template>
  <r-section
    icon="mdi-harddisk"
    :title="t('common.platforms-size')"
    elevation="0"
    titleDivider
    bgColor="bg-background"
    class="mx-2"
  >
    <template #content>
      <v-row no-gutters>
        <v-col class="pa-4" cols="12">
          <v-select
            v-model="orderBy"
            :items="[
              { title: 'Name', value: 'name' },
              { title: 'Size', value: 'size' },
            ]"
            label="Order by"
            variant="outlined"
            hide-details
          />
        </v-col>
      </v-row>
      <v-row no-gutters>
        <v-col v-for="platform in sortedPlatforms" cols="12" class="pa-4">
          <v-row no-gutters class="d-flex justify-space-between align-center">
            <v-col cols="6">
              <platform-list-item
                :platform="platform"
                :key="platform.slug"
                :showRomCount="false"
              />
            </v-col>
            <v-col cols="6" class="text-right">
              <v-list-item>
                <v-list-item-title class="text-body-2">
                  {{ formatBytes(Number(platform.fs_size_bytes)) }}
                  ({{
                    getPlatformPercentage(
                      platform.fs_size_bytes,
                      props.total_filesize,
                    ).toFixed(1)
                  }}%)
                </v-list-item-title>
                <v-list-item-subtitle class="text-right mt-1">
                  {{ platform.rom_count }} roms
                </v-list-item-subtitle>
              </v-list-item>
            </v-col>
          </v-row>
          <v-progress-linear
            :model-value="
              getPlatformPercentage(
                platform.fs_size_bytes,
                props.total_filesize,
              )
            "
            rounded
            color="primary"
            height="8"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
