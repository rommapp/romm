<script setup lang="ts">
import FabMenu from "@/components/Gallery/FabBar/FabMenu.vue";
import storeRoms from "@/stores/roms";
import storeGalleryView from "@/stores/galleryView";
import type { Events } from "@/types/emitter";
import { storeToRefs } from "pinia";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const romsStore = storeRoms();
const galleryViewStore = storeGalleryView();
const { scrolledToTop } = storeToRefs(galleryViewStore);
const { selectedRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const fabMenu = ref(false);
emitter?.on("openFabMenu", (open) => {
  fabMenu.value = open;
});

// Functions
function scrollToTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
  scrolledToTop.value = true;
}
</script>

<template>
  <v-layout-item
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
          <template #activator="{ props }">
            <v-fab-transition>
              <v-btn
                v-show="selectedRoms.length > 0"
                color="romm-accent-1"
                v-bind="props"
                elevation="8"
                class="ml-2"
                icon
                size="large"
                >{{ selectedRoms.length }}</v-btn
              >
            </v-fab-transition>
          </template>

          <fab-menu />
        </v-menu>
      </v-col>
    </v-row>
  </v-layout-item>
</template>
