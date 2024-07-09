<script setup lang="ts">
import CreateUserDialog from "@/components/Administration/Users/Dialog/CreateUser.vue";
import DeleteUserDialog from "@/components/Administration/Users/Dialog/DeleteUser.vue";
import EditUserDialog from "@/components/Administration/Users/Dialog/EditUser.vue";
import CreateExclusionDialog from "@/components/Management/Dialog/CreateExclusion.vue";
import CreatePlatformBindingDialog from "@/components/Management/Dialog/CreatePlatformBinding.vue";
import CreatePlatformVersionDialog from "@/components/Management/Dialog/CreatePlatformVersion.vue";
import DeletePlatformBindingDialog from "@/components/Management/Dialog/DeletePlatformBinding.vue";
import DeletePlatformVersionDialog from "@/components/Management/Dialog/DeletePlatformVersion.vue";
import AddRomsToCollectionDialog from "@/components/common/Collection/Dialog/AddRoms.vue";
import CreateCollectionDialog from "@/components/common/Collection/Dialog/CreateCollection.vue";
import DeleteCollectionDialog from "@/components/common/Collection/Dialog/DeleteCollection.vue";
import EditCollectionDialog from "@/components/common/Collection/Dialog/EditCollection.vue";
import RemoveRomsFromCollectionDialog from "@/components/common/Collection/Dialog/RemoveRoms.vue";
import DeleteAssetDialog from "@/components/common/Game/Dialog/Asset/DeleteAssets.vue";
import CopyRomDownloadLinkDialog from "@/components/common/Game/Dialog/CopyDownloadLink.vue";
import DeleteRomDialog from "@/components/common/Game/Dialog/DeleteRom.vue";
import EditRomDialog from "@/components/common/Game/Dialog/EditRom.vue";
import MatchRomDialog from "@/components/common/Game/Dialog/MatchRom.vue";
import SearchRomDialog from "@/components/common/Game/Dialog/SearchRom.vue";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import LoadingView from "@/components/common/LoadingView.vue";
import CollectionsDrawer from "@/components/common/Navigation/CollectionsDrawer.vue";
import MainAppBar from "@/components/common/Navigation/MainAppBar.vue";
import MainDrawer from "@/components/common/Navigation/MainDrawer.vue";
import PlatformsDrawer from "@/components/common/Navigation/PlatformsDrawer.vue";
import SettingsDrawer from "@/components/common/Navigation/SettingsDrawer.vue";
import NewVersion from "@/components/common/NewVersion.vue";
import DeletePlatformDialog from "@/components/common/Platform/Dialog/DeletePlatform.vue";
import SearchCoverDialog from "@/components/common/SearchCover.vue";
import collectionApi from "@/services/api/collection";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import gamepadService from "@/services/gamepad";
import storeAuth from "@/stores/auth";
import storeCollections from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount, onMounted, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
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
          (collection) => collection.name.toLowerCase() === "favourites"
        )
      );
    })
    .catch((error) => {
      console.error(error);
    });
  await userApi
    .fetchCurrentUser()
    .then(({ data: user }) => {
      auth.setUser(user);
    })
    .catch((error) => {
      console.error(error);
    });
  navigationStore.resetDrawers();
});

// Gamepad testing
const gamepads = ref<{ [index: number]: Gamepad }>({});

const MapABXY = [
  "mdi-alpha-a-circle",
  "mdi-alpha-b-circle",
  "mdi-alpha-x-circle",
  "mdi-alpha-y-circle",
];

const MapTriggers = [
  "mdi-alpha-l-box-outline",
  "mdi-alpha-r-box-outline",
  "mdi-alpha-l-box",
  "mdi-alpha-r-box",
];

const MapDPad = [
  "mdi-arrow-up",
  "mdi-arrow-down",
  "mdi-arrow-left",
  "mdi-arrow-right",
];

function pollGamepads() {
  gamepads.value = { ...gamepadService.getGamepads() }; // Using spread to ensure reactivity
  gamepadService.handleButtonPress(); // Check for button presses
  requestAnimationFrame(pollGamepads);
}
onMounted(async () => {
  pollGamepads();
});
</script>

<template>
  <main-drawer v-if="!smAndDown" />

  <main-app-bar v-if="smAndDown" />

  <platforms-drawer />

  <collections-drawer />

  <settings-drawer />

  <new-version />
  <v-card elevation="0">
    <v-card-text v-for="(gamepad, index) in gamepads" :key="index">
      <span class="text-h6">Gamepad {{ index + 1 }}: {{ gamepad.id }}</span
      ><v-btn
        variant="tonal"
        size="small"
        class="ml-2"
        @click="
          gamepad.vibrationActuator.playEffect('trigger-rumble', {
            startDelay: 0,
            duration: 200,
            weakMagnitude: 1.0,
            strongMagnitude: 1.0,
          })
        "
        >test vibration</v-btn
      >
      <v-divider class="mt-1 mb-3" />
      <v-row no-gutters>
        <v-col cols="2">
          <div
            v-for="(button, buttonIndex) in gamepad.buttons.slice(0, 4)"
            :key="buttonIndex"
          >
            <v-icon :class="{ 'text-romm-accent-1': button.value }">{{
              MapABXY[buttonIndex]
            }}</v-icon>
          </div>
        </v-col>
        <v-col cols="2">
          <div
            v-for="(button, buttonIndex) in gamepad.buttons.slice(4, 8)"
            :key="buttonIndex"
          >
            <v-icon :class="{ 'text-romm-accent-1': button.value == 1 }">{{
              MapTriggers[buttonIndex]
            }}</v-icon>{{ button.value < 1 && button.value > 0 ? button.value.toFixed(2) : '' }}
          </div>
        </v-col>
        <v-col cols="2">
          <div
            v-for="(button, buttonIndex) in gamepad.buttons.slice(12, 16)"
            :key="buttonIndex"
          >
            <v-icon :class="{ 'text-romm-accent-1': button.value }">{{
              MapDPad[buttonIndex]
            }}</v-icon>
          </div>
        </v-col>
      </v-row>
      <v-divider class="my-3" />
      <span>Axes: {{ gamepad.axes.join(", ") }}</span>
    </v-card-text>
  </v-card>
  <router-view />

  <delete-platform-dialog />
  <create-collection-dialog />
  <edit-collection-dialog />
  <add-roms-to-collection-dialog />
  <remove-roms-from-collection-dialog />
  <delete-collection-dialog />
  <search-rom-dialog />
  <match-rom-dialog />
  <search-cover-dialog />
  <copy-rom-download-link-dialog />
  <upload-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <delete-asset-dialog />
  <create-platform-binding-dialog />
  <delete-platform-binding-dialog />
  <create-platform-version-dialog />
  <delete-platform-version-dialog />
  <create-exclusion-dialog />
  <create-user-dialog />
  <edit-user-dialog />
  <delete-user-dialog />
  <loading-view />
</template>
<style scoped>
.v-progress-linear {
  z-index: 9999 !important;
}
</style>
