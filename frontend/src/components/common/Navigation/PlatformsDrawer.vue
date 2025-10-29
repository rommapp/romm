<script setup lang="ts">
import { useActiveElement, useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import storeNavigation from "@/stores/navigation";
import storePlatforms, { type Platform } from "@/stores/platforms";

type GroupByType = "family_name" | "generation" | "category" | null;

const { t } = useI18n();
const { mdAndUp, smAndDown } = useDisplay();
const activeElement = useActiveElement();
const navigationStore = storeNavigation();
const platformsStore = storePlatforms();
const { filteredPlatforms, filterText } = storeToRefs(platformsStore);
const { activePlatformsDrawer } = storeToRefs(navigationStore);
const openPanels = ref<number[]>([]);
const groupByRef = useLocalStorage<GroupByType | null>(
  "settings.platformsGroupBy",
  null,
);

const tabIndex = computed(() => (activePlatformsDrawer.value ? 0 : -1));

const sortedGroupedPlatforms = computed(() => {
  if (!groupByRef.value) return null;

  const groups: Record<string, Platform[]> = {};

  // Group platforms
  filteredPlatforms.value.forEach((platform) => {
    let key = platform[groupByRef.value!] || "Other";
    if (groupByRef.value === "generation" && key === -1) key = "Other";

    if (!groups[key]) groups[key] = [];
    groups[key].push(platform);
  });

  // Sort platforms within groups and return sorted entries
  return Object.entries(groups)
    .map(
      ([groupName, platforms]) =>
        [
          groupName,
          platforms.sort((a, b) => {
            // Sort platforms by generation within the same family
            if (groupByRef.value === "family_name") {
              const aGen = a.generation ?? -1;
              const bGen = b.generation ?? -1;
              if (aGen > bGen) return 1;
              if (aGen < bGen) return -1;
            }
            return a.display_name.localeCompare(b.display_name);
          }),
        ] as [string, Platform[]],
    )
    .sort(([a], [b]) => {
      if (a === "Other") return 1;
      if (b === "Other") return -1;
      return a.localeCompare(b);
    });
});

const getGroupTitle = (group: string): string => {
  if (groupByRef.value === "generation" && group !== "Other") {
    return `Gen ${group}`;
  }
  if (groupByRef.value === "category" && group === "Portable Console") {
    return "Handheld Console";
  }
  return group;
};

watch(
  sortedGroupedPlatforms,
  (newGroups) => {
    if (newGroups) {
      openPanels.value = newGroups.map((_, index) => index);
    }
  },
  { immediate: true },
);

const triggerElement = ref<HTMLElement | null | undefined>(undefined);
watch(activePlatformsDrawer, (isOpen) => {
  if (isOpen) {
    // Store the currently focused element before opening the drawer
    triggerElement.value = activeElement.value;
  }
});

const clear = () => {
  filterText.value = "";
};

const onClose = () => {
  activePlatformsDrawer.value = false;
  // Refocus the trigger element for keyboard navigation
  triggerElement.value?.focus();
};
</script>

<template>
  <v-navigation-drawer
    v-model="activePlatformsDrawer"
    mobile
    :location="smAndDown ? 'bottom' : 'left'"
    width="500"
    :class="{
      'my-2': mdAndUp || (smAndDown && activePlatformsDrawer),
      'ml-2': (mdAndUp && activePlatformsDrawer) || smAndDown,
      'drawer-mobile': smAndDown,
      'unset-height': mdAndUp,
    }"
    class="bg-surface pa-1"
    rounded
    :border="0"
    @update:model-value="clear"
    @keydown.esc="onClose"
  >
    <template #prepend>
      <v-text-field
        v-model="filterText"
        :label="t('platform.search-platform')"
        :tabindex="tabIndex"
        aria-label="Search platform"
        prepend-inner-icon="mdi-filter-outline"
        variant="solo-filled"
        density="compact"
        single-line
        hide-details
        clearable
        @click:clear="clear"
      />
    </template>

    <!-- Grouped view -->
    <v-expansion-panels
      v-if="sortedGroupedPlatforms"
      v-model="openPanels"
      class="mt-2"
      multiple
      flat
      variant="accordion"
      tabindex="-1"
    >
      <v-expansion-panel
        v-for="[group, platforms] in sortedGroupedPlatforms"
        :key="group"
        tabindex="-1"
      >
        <v-expansion-panel-title :tabindex="tabIndex" color="toplayer" static>
          {{ getGroupTitle(group) }}
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list tabindex="-1" lines="two" class="py-1 px-0">
            <PlatformListItem
              v-for="platform in platforms"
              :key="platform.slug"
              :platform="platform"
              :tabindex="tabIndex"
              :aria-label="`${platform.display_name} with ${platform.rom_count} games`"
              role="listitem"
              with-link
            />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Flat list view -->
    <v-list v-else tabindex="-1" lines="two" class="py-1 px-0">
      <PlatformListItem
        v-for="platform in filteredPlatforms"
        :key="platform.slug"
        :platform="platform"
        :tabindex="tabIndex"
        :aria-label="`${platform.display_name} with ${platform.rom_count} games`"
        role="listitem"
        with-link
      />
    </v-list>
  </v-navigation-drawer>
</template>
