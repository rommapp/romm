<script setup lang="ts">
// GlobalDialogs — the stack of emitter-driven dialogs + notification
// mount-points that need to live at the layout level so they overlay
// every route. All surfaces here are v2-native.
import AboutDialog from "@/v2/components/Dialogs/AboutDialog.vue";
import AddPhysicalGameDialog from "@/v2/components/Dialogs/AddPhysicalGameDialog.vue";
import ChangelogDialog from "@/v2/components/Dialogs/ChangelogDialog.vue";
import CopyDownloadLinkDialog from "@/v2/components/Dialogs/CopyDownloadLinkDialog.vue";
import CreateSmartCollectionDialog from "@/v2/components/Dialogs/CreateSmartCollectionDialog.vue";
import DeleteManualDialog from "@/v2/components/Dialogs/DeleteManualDialog.vue";
import DeleteRomDialog from "@/v2/components/Dialogs/DeleteRomDialog.vue";
import EditRomDialog from "@/v2/components/Dialogs/EditRomDialog.vue";
import ManageCollectionsDialog from "@/v2/components/Dialogs/ManageCollectionsDialog.vue";
import ManualUploadTargetDialog from "@/v2/components/Dialogs/ManualUploadTargetDialog.vue";
import MatchRomDialog from "@/v2/components/Dialogs/MatchRomDialog.vue";
import RefreshMetadataDialog from "@/v2/components/Dialogs/RefreshMetadataDialog.vue";
import SearchCoverDialog from "@/v2/components/Dialogs/SearchCoverDialog.vue";
import ShowQRCodeDialog from "@/v2/components/Dialogs/ShowQRCodeDialog.vue";
import NewVersionBanner from "@/v2/components/Notifications/NewVersionBanner.vue";
import NotificationHost from "@/v2/components/Notifications/NotificationHost.vue";
import UploadProgressToast from "@/v2/components/Notifications/UploadProgressToast.vue";
import EmulatorJSCacheDialog from "@/v2/components/Player/EmulatorJSCacheDialog.vue";
import SelectSaveDialog from "@/v2/components/Player/SelectSaveDialog.vue";
import SelectStateDialog from "@/v2/components/Player/SelectStateDialog.vue";
import ConfirmDialog from "@/v2/components/shared/ConfirmDialog.vue";

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
  <CopyDownloadLinkDialog />
  <ManageCollectionsDialog />
  <CreateSmartCollectionDialog />
  <AddPhysicalGameDialog />
  <AboutDialog />
  <ChangelogDialog />
  <SelectSaveDialog />
  <SelectStateDialog />
  <EmulatorJSCacheDialog />
</template>
