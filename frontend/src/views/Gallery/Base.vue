<script setup lang="ts">
import GalleryAppBar from "@/components/Gallery/AppBar/Base.vue";
import FabMenu from "@/components/Gallery/FabMenu/Base.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import GameDataTable from "@/components/Game/DataTable/Base.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms from "@/stores/roms";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { RomSelectEvent } from "@/types/rom";
import { normalizeString, views } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from "vue-router";

// Props
const route = useRoute();
const galleryViewStore = storeGalleryView();
const galleryFilterStore = storeGalleryFilter();
const gettingRoms = ref(false);
const fabMenu = ref(false);
const scrolledToTop = ref(true);
const platforms = storePlatforms();
const romsStore = storeRoms();
const {
  allRoms,
  filteredRoms,
  selectedRoms,
  searchRoms,
  platformID,
  itemsPerBatch,
} = storeToRefs(romsStore);
const itemsShown = ref(itemsPerBatch.value);
const noPlatformError = ref(false);

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filter", onFilterChange);
emitter?.on("openFabMenu", (open) => {
  fabMenu.value = open;
});

// Functions
async function fetchRoms() {
  if (gettingRoms.value) return;

  gettingRoms.value = true;
  emitter?.emit("showLoadingDialog", {
    loading: gettingRoms.value,
    scrim: false,
  });

  await romApi
    .getRoms({
      platformId: platformID.value,
      searchTerm: normalizeString(galleryFilterStore.filterSearch),
    })
    .then(({ data }) => {
      // Add any new roms to the store
      const allRomsSet = [...allRoms.value, ...data.items];
      romsStore.set(allRomsSet);
      romsStore.setFiltered(allRomsSet, galleryFilterStore);

      if (galleryFilterStore.isFiltered()) {
        const serchedRomsSet = [...searchRoms.value, ...data.items];
        romsStore.setSearch(serchedRomsSet);
        romsStore.setFiltered(serchedRomsSet, galleryFilterStore);
      }
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms for platform ID ${platformID.value}: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      console.error(
        `Couldn't fetch roms for platform ID ${platformID.value}: ${error}`
      );
    })
    .finally(() => {
      gettingRoms.value = false;
      emitter?.emit("showLoadingDialog", {
        loading: gettingRoms.value,
        scrim: false,
      });
    });
}

async function onFilterChange() {
  romsStore.setSearch([]);
  if (!galleryFilterStore.isFiltered()) {
    romsStore.setFiltered(allRoms.value, galleryFilterStore);
    return;
  }
  await fetchRoms();
  emitter?.emit("updateDataTablePages", null);
}

function selectRom({ event, index, selected }: RomSelectEvent) {
  // Add rom to selected roms
  if (event.shiftKey) {
    const [start, end] = [romsStore.lastSelectedIndex, index].sort(
      (a, b) => a - b
    );
    if (selected) {
      for (let i = start + 1; i < end; i++) {
        romsStore.addToSelection(filteredRoms.value[i]);
      }
    } else {
      for (let i = start; i <= end; i++) {
        romsStore.removeFromSelection(filteredRoms.value[i]);
      }
    }
    romsStore.updateLastSelected(selected ? index : index - 1);
  } else {
    romsStore.updateLastSelected(index);
  }
}

function setFilters() {
  galleryFilterStore.setFilterGenre([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.genres.map((genre) => genre))
        .sort()
    ),
  ]);
  galleryFilterStore.setFilterFranchise([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.franchises.map((franchise) => franchise))
        .sort()
    ),
  ]);
  galleryFilterStore.setFilterCompany([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.companies.map((company) => company))
        .sort()
    ),
  ]);
  galleryFilterStore.setFilterCollection([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.collections.map((collection) => collection))
        .sort()
    ),
  ]);
}

function resetGallery() {
  romsStore.reset();
  scrolledToTop.value = true;
  galleryFilterStore.reset();
  itemsShown.value = itemsPerBatch.value;
}

function scrollToTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
  scrolledToTop.value = true;
}

function onScroll() {
  window.setTimeout(async () => {
    const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
    scrolledToTop.value = scrollTop === 0;
    const totalScrollableHeight = scrollHeight - clientHeight;
    const ninetyPercentPoint = totalScrollableHeight * 0.9;
    if (
      scrollTop >= ninetyPercentPoint &&
      itemsShown.value < filteredRoms.value.length
    ) {
      itemsShown.value = itemsShown.value + itemsPerBatch.value;
      setFilters();
    }
  }, 100);
}

onMounted(async () => {
  const storedPlatformID = romsStore.platformID;
  const platformID = Number(route.params.platform);

  romsStore.setPlatformID(platformID);

  const platform = platforms.get(platformID);
  if (!platform) {
    // const { data } =
    await platformApi
      .getPlatform(platformID)
      .then((data) => {
        platforms.add(data.data);
      })
      .catch((error) => {
        console.log(error);
        noPlatformError.value = true;
      });
  }

  // If platform is different, reset store and fetch roms
  if (storedPlatformID != platformID) {
    resetGallery();
    await fetchRoms();
  }

  // If platform is the same but there are no roms, fetch them
  if (filteredRoms.value.length == 0) {
    await fetchRoms();
  }
  setFilters();

  window.addEventListener("wheel", onScroll);
  window.addEventListener("touchstart", onScroll);
});

onBeforeUnmount(() => {
  window.removeEventListener("wheel", onScroll);
  window.removeEventListener("touchstart", onScroll);
});

onBeforeRouteLeave((to, from, next) => {
  if (!to.fullPath.includes(from.path)) {
    resetGallery();
  }
  next();
});

onBeforeRouteUpdate(async (to, _) => {
  // Triggers when change query param of the same route
  // Reset store if switching to another platform
  resetGallery();

  const platformID = Number(to.params.platform);
  romsStore.setPlatformID(platformID);

  const platform = platforms.get(platformID);
  if (!platform) {
    const { data } = await platformApi.getPlatform(platformID);
    platforms.add(data);
  }

  await fetchRoms();
  setFilters();
});
</script>

<template>
  <gallery-app-bar />

  <template v-if="filteredRoms.length > 0">
    <v-row class="pa-1" no-gutters>
      <!-- Gallery cards view -->
      <!-- v-show instead of v-if to avoid recalculate on view change -->
      <v-col
        class="pa-1"
        v-show="galleryViewStore.current != 2"
        :cols="views[galleryViewStore.current]['size-cols']"
        :xs="views[galleryViewStore.current]['size-xs']"
        :sm="views[galleryViewStore.current]['size-sm']"
        :md="views[galleryViewStore.current]['size-md']"
        :lg="views[galleryViewStore.current]['size-lg']"
        :xl="views[galleryViewStore.current]['size-xl']"
        v-for="rom in filteredRoms.slice(0, itemsShown)"
        :key="rom.id"
      >
        <game-card
          :rom="rom"
          :index="filteredRoms.indexOf(rom)"
          :selected="selectedRoms.includes(rom)"
          :showSelector="true"
          @selectRom="selectRom"
        />
      </v-col>

      <!-- Gallery list view -->
      <v-col v-show="galleryViewStore.current == 2">
        <game-data-table />
      </v-col>
    </v-row>
  </template>

  <template v-else>
    <v-empty-state
      v-if="!gettingRoms && galleryFilterStore.isFiltered()"
      headline="No games to show"
      icon="mdi-disc-alert"
    ></v-empty-state>
  </template>

  <template v-if="noPlatformError">
    <v-empty-state
      headline="Whoops, 404"
      title="Platform not found"
      text="The platform you were looking for does not exist"
      icon="mdi-controller-off"
    ></v-empty-state>
  </template>

  <v-layout-item
    v-show="!scrolledToTop || romsStore._selectedIDs.length > 0"
    class="text-end pr-2"
    :model-value="true"
    position="bottom"
    size="65"
  >
    <v-row no-gutters>
      <v-col>
        <v-scroll-y-reverse-transition>
          <v-btn
            v-show="!scrolledToTop"
            id="scrollToTop"
            color="primary"
            elevation="8"
            icon
            class="ml-2"
            size="large"
            @click="scrollToTop()"
            ><v-icon color="romm-accent-1">mdi-chevron-up</v-icon></v-btn
          >
        </v-scroll-y-reverse-transition>
        <v-menu
          location="top"
          v-model="fabMenu"
          :transition="
            fabMenu ? 'scroll-y-reverse-transition' : 'scroll-y-transition'
          "
        >
          <template v-slot:activator="{ props }">
            <v-fab-transition>
              <v-btn
                v-show="romsStore._selectedIDs.length > 0"
                color="romm-accent-1"
                v-bind="props"
                elevation="8"
                class="ml-2"
                icon
                size="large"
                >{{ romsStore._selectedIDs.length }}</v-btn
              >
            </v-fab-transition>
          </template>

          <fab-menu />
        </v-menu>
      </v-col>
    </v-row>
  </v-layout-item>
</template>

<style scoped>
.game-card.game-selected {
  border: 2px solid rgba(var(--v-theme-romm-accent-1));
  padding: 0;
}
#scrollToTop {
  border: 1px solid rgba(var(--v-theme-romm-accent-1));
}
</style>
