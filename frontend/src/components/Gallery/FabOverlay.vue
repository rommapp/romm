<script setup lang="ts">
import collectionApi from "@/services/api/collection";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeCollections, { type Collection } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useRoute } from "vue-router";

// Props
const romsStore = storeRoms();
const galleryViewStore = storeGalleryView();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const { selectedRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const fabMenu = ref(false);
emitter?.on("openFabMenu", (open) => {
  fabMenu.value = open;
});
const auth = storeAuth();
const scanningStore = storeScanning();
const collectionsStore = storeCollections();
const { favCollection } = storeToRefs(collectionsStore);
const route = useRoute();
const heartbeat = storeHeartbeat();

// Functions
function scrollToTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
}
async function onScan() {
  scanningStore.set(true);
  const romCount = romsStore.selectedRoms.length;
  emitter?.emit("snackbarShow", {
    msg: `Scanning ${romCount} game${romCount > 1 ? "s" : ""}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [route.params.platform],
    roms_ids: romsStore.selectedRoms.map((r) => r.id),
    type: "quick", // Quick scan so we can filter by selected roms
    apis: heartbeat.getMetadataOptions().map((s) => s.value),
  });
}

function selectAllRoms() {
  romsStore.setSelection(romsStore.filteredRoms);
}

function resetSelection() {
  romsStore.resetSelection();
  emitter?.emit("openFabMenu", false);
}

async function addToFavourites() {
  if (!favCollection.value) return;
  favCollection.value.roms = favCollection.value.roms.concat(
    selectedRoms.value.map((r) => r.id)
  );
  await collectionApi
    .updateCollection({ collection: favCollection.value as Collection })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Roms added to favourites successfully!",
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}

async function removeFromFavourites() {
  if (!favCollection.value) return;
  favCollection.value.roms = favCollection.value.roms.filter(
    (value) => !selectedRoms.value.map((r) => r.id).includes(value)
  );
  if (romsStore.currentCollection?.name.toLowerCase() == "favourites") {
    romsStore.remove(selectedRoms.value);
  }
  await collectionApi
    .updateCollection({ collection: favCollection.value as Collection })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: "Roms removed from favourites successfully!",
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}

function onDownload() {
  romsStore.selectedRoms.forEach((rom, index) => {
    setTimeout(() => {
      romApi.downloadRom({ rom });
    }, index * 100); // Prevents the download from being blocked by the browser
  });
}
</script>

<template>
  <div class="text-right pa-2 sticky-bottom">
    <v-scroll-y-reverse-transition>
      <v-btn
        icon
        v-show="!scrolledToTop && currentView != 2"
        class="border-romm-accent-1"
        color="primary"
        elevation="8"
        size="large"
        @click="scrollToTop()"
        ><v-icon color="romm-accent-1">mdi-chevron-up</v-icon></v-btn
      >
    </v-scroll-y-reverse-transition>

    <v-speed-dial v-model="fabMenu" transition="slide-y-transition">
      <template #activator="{ props: menuProps }">
        <v-fab-transition>
          <v-btn
            v-show="selectedRoms.length > 0"
            class="ml-2"
            color="romm-accent-1"
            v-bind="menuProps"
            elevation="8"
            icon
            size="large"
            >{{ selectedRoms.length }}</v-btn
          >
        </v-fab-transition>
      </template>

      <v-btn
        key="1"
        v-if="auth.scopes.includes('roms.write')"
        color="terciary"
        elevation="8"
        icon
        size="default"
        @click="emitter?.emit('showDeleteRomDialog', romsStore.selectedRoms)"
      >
        <v-icon color="romm-red"> mdi-delete </v-icon>
      </v-btn>
      <v-btn
        key="2"
        v-if="auth.scopes.includes('roms.write')"
        color="terciary"
        elevation="8"
        icon="mdi-magnify-scan"
        size="default"
        @click="onScan"
      />
      <v-btn
        key="3"
        color="terciary"
        elevation="8"
        icon="mdi-download"
        size="default"
        @click="onDownload"
      />
      <v-btn
        key="4"
        color="terciary"
        elevation="8"
        :icon="
          $route.name == 'platform'
            ? 'mdi-bookmark-plus'
            : 'mdi-bookmark-remove'
        "
        size="default"
        @click="
          $route.name == 'platform'
            ? emitter?.emit('showAddToCollectionDialog', romsStore.selectedRoms)
            : emitter?.emit(
                'showRemoveFromCollectionDialog',
                romsStore.selectedRoms
              )
        "
      />
      <v-btn
        key="5"
        color="terciary"
        elevation="8"
        icon="mdi-star-outline"
        size="default"
        @click="removeFromFavourites"
      />
      <v-btn
        key="6"
        color="terciary"
        elevation="8"
        icon="mdi-star"
        size="default"
        @click="addToFavourites"
      />
      <v-btn
        key="7"
        color="terciary"
        elevation="8"
        icon="mdi-select-all"
        size="default"
        @click.stop="selectAllRoms"
      />
      <v-btn
        key="8"
        color="terciary"
        elevation="8"
        icon="mdi-select"
        size="default"
        @click.stop="resetSelection"
      />
    </v-speed-dial>
  </div>
</template>
<style scoped>
.sticky-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  z-index: 1000;
  pointer-events: none;
}
.sticky-bottom * {
    pointer-events: auto; /* Re-enables pointer events for all child elements */
}
</style>
