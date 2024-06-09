<script setup lang="ts">
import AppBar from "@/components/AppBar/Base.vue";
import DeleteAssetDialog from "@/components/Dialog/Asset/DeleteAssets.vue";
import CreateExclusionDialog from "@/components/Dialog/Config/CreateExclusion.vue";
import CreatePlatformBindingDialog from "@/components/Dialog/Config/CreatePlatformBinding.vue";
import CreatePlatformVersionDialog from "@/components/Dialog/Config/CreatePlatformVersion.vue";
import DeletePlatformBindingDialog from "@/components/Dialog/Config/DeletePlatformBinding.vue";
import DeletePlatformVersionDialog from "@/components/Dialog/Config/DeletePlatformVersion.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";
import DeletePlatformDialog from "@/components/Dialog/Platform/DeletePlatform.vue";
import ViewFirmwareDialog from "@/components/Dialog/Platform/ViewFirmware.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import MatchRomDialog from "@/components/Dialog/Rom/MatchRom/MatchRom.vue";
import CopyRomDownloadLinkDialog from "@/components/Dialog/Rom/CopyDownloadLink.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import UploadRomDialog from "@/components/Dialog/Rom/UploadRom.vue";
import CreateUserDialog from "@/components/Dialog/User/CreateUser.vue";
import DeleteUserDialog from "@/components/Dialog/User/DeleteUser.vue";
import EditUserDialog from "@/components/Dialog/User/EditUser.vue";
import Drawer from "@/components/Drawer/Base.vue";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import storeAuth from "@/stores/auth";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, onMounted } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const auth = storeAuth();
const refreshView = ref(0);

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});
emitter?.on("refreshView", async () => {
  refreshView.value = refreshView.value + 1;
});

onMounted(() => {
  userApi
    .fetchCurrentUser()
    .then(({ data: user }) => {
      auth.setUser(user);
    })
    .catch((error) => {
      console.error(error);
    });

  platformApi
    .getPlatforms()
    .then(({ data: platforms }) => {
      platformsStore.set(platforms);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>

<template>
  <v-progress-linear
    id="scan-progress-bar"
    color="romm-accent-1"
    :active="scanning"
    :indeterminate="true"
  />
  <drawer />
  <app-bar v-if="mdAndDown" />
  <router-view :key="refreshView" />

  <delete-platform-dialog />
  <search-rom-dialog />
  <match-rom-dialog />
  <copy-rom-download-link-dialog />
  <upload-rom-dialog />
  <view-firmware-dialog />
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
  <loading-dialog />
</template>

<style scoped>
#scan-progress-bar {
  z-index: 2015 !important;
  position: fixed;
}
</style>
