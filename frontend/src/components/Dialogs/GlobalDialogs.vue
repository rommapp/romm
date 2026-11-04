<script setup lang="ts">
import AboutDialog from "@/components/Dialogs/AboutDialog.vue";
import AddPhysicalGameDialog from "@/components/Dialogs/AddPhysicalGameDialog.vue";
import ChangelogDialog from "@/components/Dialogs/ChangelogDialog.vue";
import CopyDownloadLinkDialog from "@/components/Dialogs/CopyDownloadLinkDialog.vue";
import CreateSmartCollectionDialog from "@/components/Dialogs/CreateSmartCollectionDialog.vue";
import DeleteManualDialog from "@/components/Dialogs/DeleteManualDialog.vue";
import DeleteRomDialog from "@/components/Dialogs/DeleteRomDialog.vue";
import EditRomDialog from "@/components/Dialogs/EditRomDialog.vue";
import InstallOnDeviceDialog from "@/components/Dialogs/InstallOnDeviceDialog.vue";
import ManageCollectionsDialog from "@/components/Dialogs/ManageCollectionsDialog.vue";
import ManualUploadTargetDialog from "@/components/Dialogs/ManualUploadTargetDialog.vue";
import MatchRomDialog from "@/components/Dialogs/MatchRomDialog.vue";
import RefreshMetadataDialog from "@/components/Dialogs/RefreshMetadataDialog.vue";
import SearchCoverDialog from "@/components/Dialogs/SearchCoverDialog.vue";
import ShowQRCodeDialog from "@/components/Dialogs/ShowQRCodeDialog.vue";
import NewVersionBanner from "@/components/Notifications/NewVersionBanner.vue";
import NotificationHost from "@/components/Notifications/NotificationHost.vue";
import UploadProgressToast from "@/components/Notifications/UploadProgressToast.vue";
import EmulatorJSCacheDialog from "@/components/Player/EmulatorJSCacheDialog.vue";
import LoadSaveStateDialog from "@/components/Player/LoadSaveStateDialog.vue";
import ConfirmDialog from "@/components/shared/ConfirmDialog.vue";

defineOptions({ inheritAttrs: false });
</script>

<template>
  <NotificationHost />
  <UploadProgressToast />
  <NewVersionBanner />
  <ConfirmDialog />
  <ManualUploadTargetDialog />
  <DeleteManualDialog />
  <EditRomDialog />
  <DeleteRomDialog />
  <MatchRomDialog />
  <RefreshMetadataDialog />
  <SearchCoverDialog />
  <ShowQRCodeDialog />
  <InstallOnDeviceDialog />
  <CopyDownloadLinkDialog />
  <ManageCollectionsDialog />
  <CreateSmartCollectionDialog />
  <AddPhysicalGameDialog />
  <AboutDialog />
  <ChangelogDialog />
  <LoadSaveStateDialog />
  <EmulatorJSCacheDialog />
</template>
