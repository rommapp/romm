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
import UploadSavesDialog from "@/components/common/Game/Dialog/Asset/UploadSaves.vue";
import UploadStatesDialog from "@/components/common/Game/Dialog/Asset/UploadStates.vue";
import SelectSaveDialog from "@/components/common/Game/Dialog/Asset/SelectSave.vue";
import SelectStateDialog from "@/components/common/Game/Dialog/Asset/SelectState.vue";
import DeleteSavesDialog from "@/components/common/Game/Dialog/Asset/DeleteSaves.vue";
import DeleteStatesDialog from "@/components/common/Game/Dialog/Asset/DeleteStates.vue";
import NoteDialog from "@/components/common/Game/Dialog/NoteDialog.vue";
import storeCollections from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount, onMounted, ref } from "vue";
import { isNull } from "lodash";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";

const route = useRoute();
const navigationStore = storeNavigation();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();
const fetchedType = ref<string | null>(null);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  platformsStore.fetchPlatforms();
});

const showVirtualCollections = isNull(
  localStorage.getItem("settings.showVirtualCollections"),
)
  ? true
  : localStorage.getItem("settings.showVirtualCollections") === "true";

const storedVirtualCollectionType = localStorage.getItem(
  "settings.virtualCollectionType",
);
const virtualCollectionTypeRef = ref(
  isNull(storedVirtualCollectionType)
    ? "collection"
    : storedVirtualCollectionType,
);

function fetchData() {
  if (fetchedType.value !== "platform") {
    platformsStore.fetchPlatforms();
  }
  if (fetchedType.value !== "collection") {
    collectionsStore.fetchCollections();
  }
  if (fetchedType.value !== "smart") {
    collectionsStore.fetchSmartCollections();
  }
  if (fetchedType.value !== "virtual") {
    collectionsStore.fetchVirtualCollections(virtualCollectionTypeRef.value);
  }

  navigationStore.reset();

  document.removeEventListener("network-quiesced", fetchData);
}

onBeforeMount(async () => {
  document.addEventListener("network-quiesced", fetchData);

  if (route.name == ROUTES.COLLECTION) {
    collectionsStore.fetchCollections();
    fetchedType.value = "collection";
  } else if (
    showVirtualCollections &&
    route.name == ROUTES.VIRTUAL_COLLECTION
  ) {
    collectionsStore.fetchVirtualCollections(virtualCollectionTypeRef.value);
    fetchedType.value = "virtual";
  } else if (route.name == ROUTES.SMART_COLLECTION) {
    collectionsStore.fetchSmartCollections();
    fetchedType.value = "smart";
  } else {
    platformsStore.fetchPlatforms();
    fetchedType.value = "platform";
  }
});

onMounted(() => {
  // Hack to prevent main page transition on first load
  const main = document.getElementById("main");
  if (main) main.classList.remove("no-transition");
});
</script>

<template>
  <notification />
  <main-app-bar />
  <router-view />

  <match-rom-dialog />
  <edit-rom-dialog />
  <search-cover-dialog />
  <add-roms-to-collection-dialog />
  <remove-roms-from-collection-dialog />
  <delete-rom-dialog />
  <edit-user-dialog />
  <note-dialog />
  <show-q-r-code-dialog />

  <new-version-dialog />
  <upload-progress />

  <upload-saves-dialog />
  <delete-saves-dialog />
  <upload-states-dialog />
  <delete-states-dialog />
  <select-save-dialog />
  <select-state-dialog />
</template>
