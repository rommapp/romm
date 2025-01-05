<script setup lang="ts">
import EditUserDialog from "@/components/Settings/Administration/Users/Dialog/EditUser.vue";
import AddRomsToCollectionDialog from "@/components/common/Collection/Dialog/AddRoms.vue";
import RemoveRomsFromCollectionDialog from "@/components/common/Collection/Dialog/RemoveRoms.vue";
import DeleteRomDialog from "@/components/common/Game/Dialog/DeleteRom.vue";
import EditRomDialog from "@/components/common/Game/Dialog/EditRom.vue";
import MatchRomDialog from "@/components/common/Game/Dialog/MatchRom.vue";
import MainAppBar from "@/components/common/Navigation/MainAppBar.vue";
import NewVersionDialog from "@/components/common/NewVersionDialog.vue";
import Notification from "@/components/common/Notifications/Notification.vue";
import UploadProgress from "@/components/common/Notifications/UploadProgress.vue";
import SearchCoverDialog from "@/components/common/SearchCover.vue";
import ShowQRCodeDialog from "@/components/common/Game/Dialog/ShowQRCode.vue";
import collectionApi from "@/services/api/collection";
import platformApi from "@/services/api/platform";
import storeCollections from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount } from "vue";

// Props
const navigationStore = storeNavigation();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});

// Functions
onBeforeMount(async () => {
  await platformApi
    .getPlatforms()
    .then(({ data: platforms }) => {
      platformsStore.set(platforms);
    })
    .catch((error) => {
      console.error(error);
    });
  await collectionApi
    .getCollections()
    .then(({ data: collections }) => {
      collectionsStore.set(collections);
      collectionsStore.setFavCollection(
        collections.find(
          (collection) => collection.name.toLowerCase() === "favourites",
        ),
      );
    })
    .catch((error) => {
      console.error(error);
    });
  navigationStore.resetDrawers();
});
</script>

<template>
  <notification />

  <main-app-bar />

  <!-- <view-loader /> -->
  <router-view />

  <match-rom-dialog />
  <edit-rom-dialog />
  <search-cover-dialog />
  <add-roms-to-collection-dialog />
  <remove-roms-from-collection-dialog />
  <delete-rom-dialog />
  <edit-user-dialog />
  <show-q-r-code-dialog />

  <new-version-dialog />
  <upload-progress />
</template>
