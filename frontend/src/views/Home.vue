<script setup lang="ts">
import CreateExclusionDialog from "@/components/Management/Dialog/CreateExclusion.vue";
import CreatePlatformBindingDialog from "@/components/Management/Dialog/CreatePlatformBinding.vue";
import CreatePlatformVersionDialog from "@/components/Management/Dialog/CreatePlatformVersion.vue";
import DeletePlatformBindingDialog from "@/components/Management/Dialog/DeletePlatformBinding.vue";
import DeletePlatformVersionDialog from "@/components/Management/Dialog/DeletePlatformVersion.vue";
import DeletePlatformDialog from "@/components/common/Platform/Dialog/DeletePlatform.vue";
import CopyRomDownloadLinkDialog from "@/components/common/Game/Dialog/CopyDownloadLink.vue";
import DeleteRomDialog from "@/components/common/Game/Dialog/DeleteRom.vue";
import EditRomDialog from "@/components/common/Game/Dialog/EditRom.vue";
import MatchRomDialog from "@/components/common/Game/Dialog/MatchRom.vue";
import SearchRomDialog from "@/components/common/Game/Dialog/SearchRom.vue";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import CreateUserDialog from "@/components/Administration/Users/Dialog/CreateUser.vue";
import DeleteUserDialog from "@/components/Administration/Users/Dialog/DeleteUser.vue";
import EditUserDialog from "@/components/Administration/Users/Dialog/EditUser.vue";
import AppBar from "@/components/common/AppBar.vue";
import DeleteAssetDialog from "@/components/common/Game/Dialog/Asset/DeleteAssets.vue";
import LoadingView from "@/components/common/LoadingView.vue";
import NewVersion from "@/components/common/NewVersion.vue";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, ref } from "vue";

// Props
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const auth = storeAuth();
const refreshView = ref(0);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});
emitter?.on("refreshView", async () => {
  refreshView.value = refreshView.value + 1;
});

// Functions
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
    color="romm-accent-1"
    :active="scanning"
    :indeterminate="true"
    absolute
  />
  <app-bar />
  <new-version />
  <router-view :key="refreshView" />

  <delete-platform-dialog />
  <search-rom-dialog />
  <match-rom-dialog />
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
