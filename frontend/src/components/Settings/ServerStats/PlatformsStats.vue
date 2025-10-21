<script setup lang="ts">
import { storeToRefs } from "pinia";
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import RSection from "@/components/common/RSection.vue";
import storePlatforms from "@/stores/platforms";
import { formatBytes } from "@/utils";

const props = defineProps<{
  totalFilesize: number;
}>();
const { t } = useI18n();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const orderBy = ref<"name" | "size" | "count">("name");

const sortedPlatforms = computed(() => {
  if (orderBy.value === "size") {
    return allPlatforms.value.sort(
      (a, b) => Number(b.fs_size_bytes) - Number(a.fs_size_bytes),
    );
  }
  if (orderBy.value === "count") {
    return allPlatforms.value.sort((a, b) => b.rom_count - a.rom_count);
  }
  return allPlatforms.value.sort((a, b) =>
    a.display_name.localeCompare(b.display_name, undefined, {
      sensitivity: "base",
    }),
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
  <RSection
    icon="mdi-harddisk"
    :title="t('common.platforms-size')"
    elevation="0"
    title-divider
    bg-color="bg-background"
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
              { title: 'Count', value: 'count' },
            ]"
            label="Order by"
            variant="outlined"
            hide-details
          />
        </v-col>
      </v-row>
      <v-row no-gutters>
        <v-col
          v-for="platform in sortedPlatforms"
          :key="platform.slug"
          cols="12"
          class="pa-4"
        >
          <v-row no-gutters class="d-flex justify-space-between align-center">
            <v-col cols="6">
              <PlatformListItem
                :key="platform.slug"
                :platform="platform"
                :show-rom-count="false"
              />
            </v-col>
            <v-col cols="6" class="text-right">
              <v-list-item>
                <v-list-item-title class="text-body-2">
                  {{ formatBytes(Number(platform.fs_size_bytes)) }}
                  ({{
                    getPlatformPercentage(
                      platform.fs_size_bytes,
                      props.totalFilesize,
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
              getPlatformPercentage(platform.fs_size_bytes, props.totalFilesize)
            "
            rounded
            color="primary"
            height="8"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
