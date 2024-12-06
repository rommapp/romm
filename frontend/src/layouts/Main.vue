<script setup lang="ts">
import EditUserDialog from "@/components/Settings/Administration/Users/Dialog/EditUser.vue";
import AddRomsToCollectionDialog from "@/components/common/Collection/Dialog/AddRoms.vue";
import RemoveRomsFromCollectionDialog from "@/components/common/Collection/Dialog/RemoveRoms.vue";
import DeleteRomDialog from "@/components/common/Game/Dialog/DeleteRom.vue";
import EditRomDialog from "@/components/common/Game/Dialog/EditRom.vue";
import MatchRomDialog from "@/components/common/Game/Dialog/MatchRom.vue";
import SearchRomDialog from "@/components/common/Game/Dialog/SearchRom.vue";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import CollectionsDrawer from "@/components/common/Navigation/CollectionsDrawer.vue";
import MainAppBar from "@/components/common/Navigation/MainAppBar.vue";
import MainDrawer from "@/components/common/Navigation/MainDrawer.vue";
import PlatformsDrawer from "@/components/common/Navigation/PlatformsDrawer.vue";
import SettingsDrawer from "@/components/common/Navigation/SettingsDrawer.vue";
import NewVersionDialog from "@/components/common/NewVersionDialog.vue";
import Notification from "@/components/common/Notifications/Notification.vue";
import UploadProgress from "@/components/common/Notifications/UploadProgress.vue";
import SearchCoverDialog from "@/components/common/SearchCover.vue";
import ViewLoader from "@/components/common/ViewLoader.vue";
import router from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import api from "@/services/api/index";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeCollections from "@/stores/collections";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount } from "vue";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
const heartbeat = storeHeartbeat();
const configStore = storeConfig();
const navigationStore = storeNavigation();
const auth = storeAuth();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});

// Functions
onBeforeMount(async () => {
  await api.get("/heartbeat").then(async ({ data: data }) => {
    heartbeat.set(data);
    if (heartbeat.value.SHOW_SETUP_WIZARD) {
      router.push({ name: "setup" });
    } else {
      await userApi
        .fetchCurrentUser()
        .then(({ data: user }) => {
          auth.setUser(user);
        })
        .catch((error) => {
          console.error(error);
        });

      await api.get("/config").then(({ data: data }) => {
        configStore.set(data);
      });
    }
  });

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

  <template v-if="!smAndDown">
    <main-drawer />
  </template>
  <template v-else>
    <main-app-bar />
  </template>
  <search-rom-dialog />
  <platforms-drawer />
  <collections-drawer />
  <upload-rom-dialog />
  <settings-drawer />

  <view-loader />
  <router-view />

  <match-rom-dialog />
  <edit-rom-dialog />
  <search-cover-dialog />
  <add-roms-to-collection-dialog />
  <remove-roms-from-collection-dialog />
  <delete-rom-dialog />
  <edit-user-dialog />

  <new-version-dialog />
  <upload-progress />
</template>
