<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { inject, onBeforeMount } from "vue";
import EditUserDialog from "@/components/Settings/Administration/Users/Dialog/EditUser.vue";
import AddRomsToCollectionDialog from "@/components/common/Collection/Dialog/AddRoms.vue";
import RemoveRomsFromCollectionDialog from "@/components/common/Collection/Dialog/RemoveRoms.vue";
import LoadingDialog from "@/components/common/Dialog/LoadingDialog.vue";
import SearchCoverDialog from "@/components/common/Dialog/SearchCover.vue";
import DeleteSavesDialog from "@/components/common/Game/Dialog/Asset/DeleteSaves.vue";
import DeleteStatesDialog from "@/components/common/Game/Dialog/Asset/DeleteStates.vue";
import SelectSaveDialog from "@/components/common/Game/Dialog/Asset/SelectSave.vue";
import SelectStateDialog from "@/components/common/Game/Dialog/Asset/SelectState.vue";
import UploadSavesDialog from "@/components/common/Game/Dialog/Asset/UploadSaves.vue";
import UploadStatesDialog from "@/components/common/Game/Dialog/Asset/UploadStates.vue";
import DeleteRomDialog from "@/components/common/Game/Dialog/DeleteRom.vue";
import EditRomDialog from "@/components/common/Game/Dialog/EditRom.vue";
import MatchRomDialog from "@/components/common/Game/Dialog/MatchRom.vue";
import NoteDialog from "@/components/common/Game/Dialog/NoteDialog.vue";
import ShowQRCodeDialog from "@/components/common/Game/Dialog/ShowQRCode.vue";
import MainAppBar from "@/components/common/Navigation/MainAppBar.vue";
import NewVersionDialog from "@/components/common/NewVersionDialog.vue";
import Notification from "@/components/common/Notifications/Notification.vue";
import UploadProgress from "@/components/common/Notifications/UploadProgress.vue";
import storeCollections from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";

const navigationStore = storeNavigation();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  platformsStore.fetchPlatforms();
});

const showVirtualCollections = useLocalStorage(
  "settings.showVirtualCollections",
  true,
);
const virtualCollectionTypeRef = useLocalStorage(
  "settings.virtualCollectionType",
  "collection",
);

function unhackNavbar() {
  document.removeEventListener("network-quiesced", unhackNavbar);

  // Hack to prevent main page transition on first load
  const main = document.getElementById("main");
  if (main) main.classList.remove("no-transition");
}

onBeforeMount(async () => {
  document.addEventListener("network-quiesced", unhackNavbar);

  platformsStore.fetchPlatforms();
  collectionsStore.fetchCollections();
  collectionsStore.fetchSmartCollections();
  if (showVirtualCollections) {
    collectionsStore.fetchVirtualCollections(virtualCollectionTypeRef.value);
  }

  navigationStore.reset();
});
</script>

<template>
  <Notification />
  <MainAppBar />
  <router-view />

  <UploadProgress />
  <LoadingDialog />
  <MatchRomDialog />
  <EditRomDialog />
  <SearchCoverDialog />
  <AddRomsToCollectionDialog />
  <RemoveRomsFromCollectionDialog />
  <DeleteRomDialog />
  <EditUserDialog />
  <NoteDialog />
  <ShowQRCodeDialog />
  <NewVersionDialog />
  <UploadSavesDialog />
  <DeleteSavesDialog />
  <UploadStatesDialog />
  <DeleteStatesDialog />
  <SelectSaveDialog />
  <SelectStateDialog />
</template>
